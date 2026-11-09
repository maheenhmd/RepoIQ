export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

// Shared by both mounted dashboard modes. No automatic generation retries.
let generationActive = false;

export async function consumeChatStream<T>(response: Response, delta: (text: string) => void,
  stage: (name: string) => void): Promise<T> {
  if (!response.ok) {
    const data = await response.json();
    throw new ApiError(typeof data.detail === 'string' ? data.detail : 'Chat unavailable', response.status);
  }
  if (!response.body) throw new ApiError('Empty stream; retry the same message.', 0);
  const reader = response.body.getReader(), decoder = new TextDecoder();
  let buffer = '', received = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }); received += value?.byteLength ?? 0;
      if (received > 100000 || buffer.length > 50000) throw new ApiError('Chat stream exceeded limit.', 502);
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary+2);
        const kind = frame.match(/^event: (.+)$/m)?.[1], encoded = frame.match(/^data: (.+)$/m)?.[1];
        if (!encoded) continue;
        const data = JSON.parse(encoded);
        if (kind === 'delta' && typeof data.text === 'string') delta(data.text);
        if (kind === 'status' && typeof data.stage === 'string') stage(data.stage);
        if (kind === 'error') throw new ApiError(data.detail ?? 'Reply could not be verified.', data.status ?? 502);
        if (kind === 'complete') return data as T;
      }
      if (done) throw new ApiError('Stream interrupted. Your draft is retained; retry the same request.', 0);
    }
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}

export async function streamChat<T>(path: string, body: unknown, delta: (text: string) => void,
  stage: (name: string) => void, signal: AbortSignal): Promise<T> {
  if (generationActive) throw new ApiError('AI is still processing another request. Your draft is retained.', 429);
  generationActive = true;
  try {
    const response = await fetch(`/api/backend/${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(body), cache: 'no-store',
      signal: AbortSignal.any([signal, AbortSignal.timeout(240000)]),
    });
    return await consumeChatStream<T>(response, delta, stage);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('Chat stopped or connection interrupted. Your draft is saved; retry the same message.', 0);
  } finally { generationActive = false; }
}

export type RepositoryLookup = {
  repository_id: string | null;
  indexing_complete: boolean;
};

export type SavedInterview = {
  session_id: string;
  status: 'active' | 'finished';
  topic: string;
  updated_at: string;
};

export const lookupRepository = (url: string) =>
  interviewApi<RepositoryLookup>('api/repositories/lookup', { url });

export const lookupInterviews = (repositoryId: string) =>
  interviewApi<SavedInterview[]>('api/interviews/lookup', { repository_id: repositoryId });

export const deleteInterview = (sessionId: string) =>
  interviewApi<void>(`api/interviews/${sessionId}`, undefined, 'DELETE');

export async function interviewApi<T>(path: string, body?: unknown, method?: 'DELETE'): Promise<T> {
  const generation = body !== undefined && !method && (
    path === 'api/interviews/start' || /^api\/interviews\/[^/]+\/answers$/.test(path) || /^api\/chats\/[^/]+\/[^/]+\/messages$/.test(path));
  if (generation && generationActive) throw new ApiError('AI is still processing another request. Your draft is retained; wait for it to finish before retrying.', 429);
  if (generation) generationActive = true;
  try {
    const response = await fetch(`/api/backend/${path}`, {
      method: method ?? (body === undefined ? 'GET' : 'POST'),
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: 'no-store', signal: AbortSignal.timeout(body === undefined ? 30000 : 240000),
    });
    if (response.status === 204) return undefined as T;
    const data = await response.json();
    if (!response.ok) throw new ApiError(typeof data.detail === 'string' ? data.detail : 'Please check your input and try again.', response.status);
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('Connection interrupted. Your answer is retained; retry the same request or reload saved history.', 0);
  } finally {
    if (generation) generationActive = false;
  }
}
