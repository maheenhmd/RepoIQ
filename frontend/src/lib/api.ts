export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function interviewApi<T>(path: string, body?: unknown): Promise<T> {
  try {
    const response = await fetch(`/api/backend/${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: 'no-store', signal: AbortSignal.timeout(240000),
    });
    const data = await response.json();
    if (!response.ok) throw new ApiError(typeof data.detail === 'string' ? data.detail : 'Please check your input and try again.', response.status);
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('Connection interrupted. Your answer is retained; retry the same request or reload saved history.', 0);
  }
}
