'use client';
import { forwardRef, useImperativeHandle, useEffect, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import Image from 'next/image';
import InterviewReport from '@/components/InterviewReport';
import { Sources } from '@/components/QuestionCard';
import { ApiError, interviewApi, lookupInterviews, lookupRepository } from '@/lib/api';
import type { SavedInterview } from '@/lib/api';
import type {
  Difficulty,
  History,
  Interview,
  Report,
  Turn,
} from '@/types';
import '@/app/interview/workspace.css';
type Pending = {
  path: string;
  body: Record<string, string | number>;
};
type SavedSession = {
  session: string | null;
  pending: Pending | null;
  answer: string;
};
const STORAGE_KEY = 'repoiq-interview';
type ImportJob = { id: string; repository_id: string; status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'; processed_files: number; total_files: number; progress_percent: number; error_summary: string | null; rate_limited: boolean; next_attempt_at: string | null };
type ImportState = { url: string; request_id: string; job?: ImportJob };
const IMPORT_KEY = 'repoiq-import';
const DEFAULT_TOPIC =
  'HTTP authentication and error handling';
export type WorkspaceHandle = { openSession: (id: string) => void; newInterview: () => void; selectRepository: (url: string) => void; forgetSession: (id: string) => void };
type WorkspaceProps = { embedded?: boolean; onUpdate?: (state: { session: Interview | null; repositoryId: string; url: string; busy: boolean }) => void };
const InterviewWorkspace = forwardRef<WorkspaceHandle, WorkspaceProps>(function InterviewWorkspace({ embedded = false, onUpdate }, ref) {
  const [current, setCurrent] = useState<Interview | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [repo, setRepo] = useState('');
  const [githubUrl, setGithubUrl] = useState('');
  const [importState, setImportState] = useState<ImportState | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [indexed, setIndexed] = useState(false);
  const [importMessage, setImportMessage] = useState('Import a public GitHub repository to begin.');
  const [pollRound, setPollRound] = useState(0);
  const [sessions, setSessions] = useState<SavedInterview[]>([]);
  const [detecting, setDetecting] = useState(false);
  useEffect(() => {
    if (current || !githubUrl.trim() || importBusy) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      setDetecting(true);
      try {
        const result = await lookupRepository(githubUrl.trim());
        if (cancelled) return;
        setRepo(result.repository_id ?? ''); setIndexed(result.indexing_complete);
        if (result.repository_id) {
          const history = await lookupInterviews(result.repository_id);
          if (cancelled) return;
          setSessions(history);
          setImportMessage(result.indexing_complete ? 'Repository found. Resume a conversation or start a new interview.' : 'Repository found; indexing is not complete.');
        } else { setSessions([]); setImportMessage('Repository not indexed yet. Import it to begin.'); }
      } catch (err) {
        if (!cancelled) { setSessions([]); setImportMessage(err instanceof Error ? err.message : 'Lookup unavailable.'); }
      } finally { if (!cancelled) setDetecting(false); }
    }, 600);
    return () => { cancelled = true; clearTimeout(timer); setDetecting(false); };
  }, [githubUrl, current, importBusy]);
  async function openSaved(id: string) {
    if (busy || lock.current) return;
    lock.current = true;
    setBusy(true); setError('');
    try {
      stashDraft();
      const loaded = await loadSession(id);
      let draft = '', retry: Pending | null = null;
      try {
        const saved = JSON.parse(sessionStorage.getItem('repoiq-draft-' + id) ?? 'null');
        draft = saved?.answer ?? ''; retry = saved?.pending ?? null;
      } catch {}
      if (retry && loaded.turns.some(turn => turn.request_id === retry?.body.request_id)) { draft = ''; retry = null; }
      setPending(retry); setAnswer(draft); saveSession(id, retry, draft);
    }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to restore conversation.'); }
    finally { lock.current = false; setBusy(false); }
  }  const importLock = useRef(false);
  function rememberImport(value: ImportState) {
    setImportState(value);
    try { localStorage.setItem(IMPORT_KEY, JSON.stringify(value)); }
    catch { setImportMessage('Browser storage unavailable; keep this tab open.'); }
  }
  async function importRepository() {
    if (importLock.current || busy || pending) return;
    let url: URL;
    try {
      url = new URL(githubUrl.trim());
      if (url.protocol !== 'https:' || url.hostname !== 'github.com' || url.port || url.username || url.password || url.search || url.hash || !/^\/[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+\/?$/.test(url.pathname)) throw new Error();
    } catch { setImportMessage('Use https://github.com/owner/repository (public repositories only).'); return; }
    const canonical = `https://github.com${url.pathname.replace(/\/$/, '').replace(/\.git$/, '')}`;
    const previous = importState;
    const request = previous && previous.url === canonical && !['failed', 'cancelled'].includes(previous.job?.status ?? '')
      ? previous : { url: canonical, request_id: crypto.randomUUID() };
    importLock.current = true; setImportBusy(true); setIndexed(false); setRepo('');
    rememberImport(request); setImportMessage('Submitting import…');
    try {
      const job = await interviewApi<ImportJob>('api/repositories/ingest', { url: request.url, request_id: request.request_id });
      rememberImport({ ...request, job }); setRepo(job.repository_id); setPollRound(n => n + 1);
    } catch (err) { setImportMessage(err instanceof Error ? err.message : 'Import unavailable. Retry safely.'); }
    finally { importLock.current = false; setImportBusy(false); }
  }
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(IMPORT_KEY) ?? sessionStorage.getItem(IMPORT_KEY) ?? 'null') as ImportState | null;
      if (saved && typeof saved.url === 'string' && saved.request_id) {
        rememberImport(saved); setGithubUrl(saved.url);
        if (saved.job) setRepo(saved.job.repository_id);
        else setImportMessage('Import response interrupted. Retry import to recover the same request.');
      }
    } catch { setImportMessage('Saved import unavailable; enter the URL again.'); }
  }, []);
  useEffect(() => {
    if (!importState?.job || current || importBusy) return;
    const saved = importState;
    const jobId = saved.job!.id;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    async function poll() {
      attempts++;
      try {
        const job = await interviewApi<ImportJob>(`api/repositories/ingest/${jobId}`);
        if (stopped) return;
        rememberImport({ ...saved, job }); setRepo(job.repository_id);
        if (job.status === 'failed' || job.status === 'cancelled') {
          setIndexed(false); setImportMessage(job.error_summary ?? `Import ${job.status}. Retry import to create a new job.`); return;
        }
        setImportMessage(job.rate_limited ? `Paused by GitHub rate limit. Next retry: ${job.next_attempt_at ? new Date(job.next_attempt_at).toLocaleString() : 'pending'}` : `${job.status === 'running' ? 'Importing files' : job.status}: ${job.processed_files}/${job.total_files} files`);
        if (job.status === 'succeeded') {
          const result = await interviewApi<{ ready: boolean; indexing_complete: boolean; total_chunks: number; embedded_chunks: number }>(`api/repositories/${job.repository_id}/ready`);
          if (stopped) return;
          setIndexed(result.indexing_complete);
          setImportMessage(result.indexing_complete ? 'Ready for interview · import and embeddings complete.' : result.total_chunks === 0 ? 'Import completed, but no code chunks are available for interviews.' : `Import completed · Generating embeddings: ${result.embedded_chunks} / ${result.total_chunks}. Ensure the embedding worker is running.`);
          if (result.indexing_complete || result.total_chunks === 0) return;
        }
      } catch (err) {
        if (stopped) return;
        setIndexed(false); setImportMessage(err instanceof Error ? err.message : 'Status unavailable.');
        if (err instanceof ApiError && err.status === 404) return;
      }
      if (attempts < 60) timer = setTimeout(poll, 5000);
      else setImportMessage('Monitoring paused. Workers may be stopped or still processing. Refresh status to resume; the job remains saved.');
    }
    void poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [importState?.job?.id, pollRound, current, importBusy]);
  const [topic, setTopic] = useState(DEFAULT_TOPIC);
  const [difficulty, setDifficulty] =
    useState<Difficulty>('intermediate');
  const maxTurns = 5; // Fixed MVP length; old sessions retain their saved limits.
  const [answer, setAnswer] = useState('');
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const lock = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);
  const navigation = useRef(0);
  function stashDraft() {
    if (current) { try { sessionStorage.setItem('repoiq-draft-' + current.session_id, JSON.stringify({ answer, pending })); } catch {} }
  }
  useImperativeHandle(ref, () => ({
    openSession: id => { if (!busy && !lock.current) void openSaved(id); },
    newInterview,
    forgetSession: id => {
      setSessions(previous => previous.filter(item => item.session_id !== id));
      try {
        sessionStorage.removeItem('repoiq-draft-' + id);
        for (const storage of [sessionStorage, localStorage]) {
          const saved = JSON.parse(storage.getItem(STORAGE_KEY) ?? 'null');
          if (saved?.session === id) storage.removeItem(STORAGE_KEY);
        }
      } catch {}
      if (current?.session_id === id) {
        navigation.current++;
        setCurrent(null); setTurns([]); setReport(null); setPending(null); setAnswer(''); setError('');
        setSettingsOpen(false);
      }
    },
    selectRepository: url => {
      if (busy || lock.current) return;
      if ((answer || pending) && !window.confirm('Switch repository? Your draft will remain saved.')) return;
      stashDraft(); navigation.current++;
      setCurrent(null); setTurns([]); setReport(null); setPending(null); setAnswer('');
      setGithubUrl(url); setImportState(null); setRepo(''); setIndexed(false);
      saveSession(null, null, '');
    },
  }));
  useEffect(() => { onUpdate?.({ session: current, repositoryId: current?.repository_id ?? repo, url: current && current.repository_id !== repo ? '' : githubUrl, busy }); }, [current, repo, githubUrl, busy, onUpdate]);
  // Keep the existing session recoverable after refresh.
  function saveSession(
    session: string | null,
    retry: Pending | null,
    draft: string
  ) {
    try {
      const data: SavedSession = {
        session,
        pending: retry,
        answer: draft,
      };
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(data)
      );
    } catch {
      // The interview can still run without browser storage.
    }
  }
  async function loadSession(sessionId: string) {
    const generation = ++navigation.current;
    const history = await interviewApi<History>(
      `api/interviews/${sessionId}`
    );
    if (generation !== navigation.current) return history;
    setCurrent(previous => previous?.session_id === history.current.session_id && previous.version > history.current.version ? previous : history.current);
    setTurns(previous => previous.length && previous[previous.length - 1].response.session_id === history.current.session_id && previous[previous.length - 1].response.version > history.current.version ? previous : history.turns);
    setReport(history.current.report ?? null);
    if (
      history.current.status === 'finished' &&
      !history.current.report
    ) {
      try {
        const result = await interviewApi<Report>(
          `api/interviews/${sessionId}/report`
        );
        if (generation === navigation.current) setReport(result);
      } catch {
        setError(
          'Interview loaded, but the report could not be loaded.'
        );
      }
    }
    return history;
  }
  // Restore previous interview.
  useEffect(() => {
    void interviewApi<{ status: string }>('ready')
      .then((data) => setReady(data.status === 'ready'))
      .catch(() => setReady(false));
    async function restore() {
      try {
        const location = new URL(window.location.href);
        if (location.searchParams.get('new') === '1') {
          sessionStorage.removeItem(STORAGE_KEY);
          location.searchParams.delete('new');
          window.history.replaceState(null, '', location.toString());
          return;
        }
        const raw = sessionStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        const saved = JSON.parse(raw) as SavedSession;
        setAnswer(saved.answer ?? '');
        setPending(saved.pending ?? null);
        if (!saved.session) return;
        try {
          const history = await loadSession(saved.session);
          const alreadySaved = saved.pending
            ? history.turns.some(
                (turn) =>
                  turn.request_id ===
                  saved.pending?.body.request_id
              )
            : false;
          if (alreadySaved) {
            setPending(null);
            setAnswer('');
            saveSession(saved.session, null, '');
          }
        } catch (err) {
          const isPendingStart =
            saved.pending?.path === 'api/interviews/start';
          if (
            !(
              isPendingStart &&
              err instanceof ApiError &&
              err.status === 404
            )
          ) {
            throw err;
          }
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Could not restore the interview.'
        );
      } finally {
        setBusy(false);
      }
    }
    void restore();
  }, []);
  // Smooth dropdown with outside-click and Escape support.
  useEffect(() => {
    if (!settingsOpen) return;
    function handleOutsideClick(event: PointerEvent) {
      if (
        settingsRef.current &&
        !settingsRef.current.contains(event.target as Node)
      ) {
        setSettingsOpen(false);
      }
    }
    function handleEscape(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape') {
        setSettingsOpen(false);
      }
    }
    document.addEventListener(
      'pointerdown',
      handleOutsideClick
    );
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener(
        'pointerdown',
        handleOutsideClick
      );
      document.removeEventListener(
        'keydown',
        handleEscape
      );
    };
  }, [settingsOpen]);
  // Use the browser's natural page scroll.
  useEffect(() => {
    if (!current || (embedded && bottomRef.current?.closest('[hidden]'))) return;
    bottomRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    });
  }, [current, turns.length, report]);
  async function fetchReport(sessionId: string) {
    const generation = navigation.current;
    try {
      const result = await interviewApi<Report>(
        `api/interviews/${sessionId}/report`
      );
      if (generation !== navigation.current) return;
      setReport(result);
      setError('');
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Could not load the final report.'
      );
    }
  }
  // Existing backend request and idempotent retry behavior.
  async function submit(request: Pending) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    setPending(request);
    const sessionId =
      current?.session_id ??
      String(request.body.request_id);
    saveSession(sessionId, request, answer);
    try {
      const response = await interviewApi<Interview>(
        request.path,
        request.body
      );
      setCurrent(previous => previous?.session_id === response.session_id && previous.version > response.version ? previous : response);
      setReport(response.report ?? null);
      setTurns((previous) => {
        const exists = previous.some(
          (turn) =>
            turn.request_id === request.body.request_id
        );
        if (exists) return previous;
        return [
          ...previous,
          {
            request_id: String(request.body.request_id),
            answer:
              typeof request.body.answer === 'string'
                ? request.body.answer
                : null,
            response,
          },
        ].sort((a, b) => a.response.version - b.response.version);
      });
      setAnswer('');
      setPending(null);
      try { sessionStorage.removeItem('repoiq-draft-' + response.session_id); } catch {}
      saveSession(response.session_id, null, '');
      if (
        response.status === 'finished' &&
        !response.report
      ) {
        await fetchReport(response.session_id);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Request failed. Please retry.'
      );
      if (err instanceof ApiError && err.status === 422) {
        setPending(null);
        saveSession(
          current?.session_id ?? null,
          null,
          answer
        );
      }
      if (err instanceof ApiError && err.status === 429) {
        setError('AI is processing another interview or repository-chat request. Your draft is saved. Wait for completion, then retry the same answer or reload conversation.');
        // Keep the draft editable after the failed request. Never automatically POST again.
      }
      if (
        err instanceof ApiError &&
        err.status === 409 &&
        current
      ) {
        try {
          const history = await loadSession(
            current.session_id
          );
          const applied = history.turns.some(
            (turn) =>
              turn.request_id ===
              request.body.request_id
          );
          setPending(null);
          if (applied) {
            setAnswer('');
            setError('');
            saveSession(current.session_id, null, '');
          } else {
            saveSession(
              current.session_id,
              null,
              answer
            );
            setError(history.current.version !== request.body.expected_version || history.current.status !== 'active'
              ? 'Interview changed. Your answer is retained. Review the latest question before sending again.'
              : err.message + ' Your question has not changed; your answer is retained.');
          }
        } catch {
          // Preserve the original request for a safe retry.
        }
      }
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  function startInterview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || importBusy || (!pending && (!indexed || !repo || !topic.trim()))) return;
    setSettingsOpen(false);
    void submit(
      pending ?? {
        path: 'api/interviews/start',
        body: {
          request_id: crypto.randomUUID(),
          repository_id: repo.trim(),
          topic: topic.trim(),
          difficulty,
          max_turns: maxTurns,
        },
      }
    );
  }
  function sendAnswer() {
    if (
      !current ||
      busy ||
      !answer.trim()
    ) {
      return;
    }
    void submit(
      pending ?? {
        path: `api/interviews/${current.session_id}/answers`,
        body: {
          request_id: crypto.randomUUID(),
          expected_version: current.version,
          answer: answer.trim(),
        },
      }
    );
  }
  function newInterview() {
    if (busy || lock.current) return;
    if (
      (current || pending || answer) &&
      !window.confirm(
        'Start a new interview? Your previous interview remains saved.'
      )
    ) {
      return;
    }
    stashDraft(); navigation.current++;
    setCurrent(null);
    setTurns([]);
    setReport(null);
    setPending(null);
    setAnswer('');
    setError('');
    setSettingsOpen(false);
    saveSession(null, null, '');
  }
  function handleAnswerKey(
    event: KeyboardEvent<HTMLTextAreaElement>
  ) {
    if (
      event.key === 'Enter' &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      sendAnswer();
    }
  }
  const progress = current
    ? Math.min(
        100,
        (current.answered_turns / current.max_turns) * 100
      )
    : 0;
  return (
    <div className={`repoiq-chat ${embedded ? 'repoiq-embedded' : ''}`}>
      {/* Minimal navigation */}
      <header className="chat-header">
        <a
          href="/"
          className="chat-brand"
          aria-label="RepoIQ home"
        >
          Repo<span>I</span><strong>Q</strong>
        </a>
        <div className="header-right">
          <span className="connection">
            <span
              className={`connection-dot ${
                ready ? 'online' : ''
              }`}
            />
            {ready ? 'AI ready' : 'AI unavailable'}
          </span>
          {(current || pending) && (
            <button
              type="button"
              className="new-interview"
              disabled={busy}
              onClick={newInterview}
            >
              <span aria-hidden="true">+</span>
              New interview
            </button>
          )}
        </div>
      </header>
      {/* Welcome / interview setup */}
      {!current ? (
        <section className="welcome-screen">
          <div className="welcome-inner">
            <div className="greeting">
              <Image
                src="/repoiq-mascot.png"
                alt="RepoIQ mascot"
                width={76}
                height={76}
                priority
                className="greeting-mascot"
              />
              <h1>
                Hi. Ready to <span>talk code?</span>
              </h1>
            </div>
            <p className="welcome-description">
              An interview grounded in your own repository.
              One question at a time.
            </p>
            <form
              className="start-composer"
              onSubmit={startInterview}
            >
              <section className="repository-onboarding" aria-label="Repository import">
                <label htmlFor="github-url">GitHub repository</label>
                <div className="import-controls"><input id="github-url" type="url" placeholder="https://github.com/owner/repository" value={githubUrl} disabled={busy || importBusy || !!pending} onChange={event => { setGithubUrl(event.target.value); setSessions([]); setIndexed(false); setRepo(''); setImportState(null); try { localStorage.removeItem(IMPORT_KEY); } catch {} }} />
                  <button type="button" disabled={busy || detecting || indexed || importBusy || !!pending || !githubUrl.trim()} onClick={() => void importRepository()}>{importBusy ? 'Importing…' : importState ? 'Retry import' : 'Import repository'}</button></div>
                <p role="status">{detecting ? 'Checking your repository…' : importMessage}</p>
                {sessions.length > 0 && <div aria-label="Saved interviews">{sessions.map(session => <button type="button" key={session.session_id} disabled={busy || detecting || !!pending} onClick={() => void openSaved(session.session_id)} style={{ margin: 4 }}>{session.status === 'finished' ? 'View Report' : 'Resume Interview'} · {session.topic} · {new Date(session.updated_at).toLocaleDateString()}</button>)}</div>}
                {importState?.job && <><progress max={100} value={importState.job.progress_percent} aria-label="Ingestion progress" /><button type="button" disabled={importBusy} onClick={() => { setIndexed(false); setPollRound(n => n + 1); }}>Refresh status</button></>}
                <small>Public repositories only. Import details persist on this browser. Both workers must run; interview starts after all repository chunks have compatible embeddings.</small>
              </section>
              <label className="sr-only" htmlFor="topic">
                Interview topic
              </label>
              <textarea
                id="topic"
                name="topic"
                rows={2}
                maxLength={120}
                required
                value={topic}
                disabled={busy || !!pending}
                placeholder="What would you like to practice?"
                onChange={(event) =>
                  setTopic(event.target.value)
                }
              />
              <div className="composer-bottom">
                <div className="composer-tools">
                  <div
                    ref={settingsRef}
                    className="settings-menu"
                  >
                    <button
                      type="button"
                      className={`settings-trigger ${
                        settingsOpen ? 'is-open' : ''
                      }`}
                      aria-expanded={settingsOpen}
                      aria-controls="interview-settings-panel"
                      onClick={() =>
                        setSettingsOpen((open) => !open)
                      }
                    >
                      <svg
                        viewBox="0 0 24 24"
                        width="17"
                        height="17"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <path d="M4 7h16M4 17h16" />
                        <circle cx="9" cy="7" r="2" fill="#292a2e" />
                        <circle cx="15" cy="17" r="2" fill="#292a2e" />
                      </svg>
                      Interview settings
                      <svg
                        className="settings-chevron"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <path d="m6 9 6 6 6-6" />
                      </svg>
                    </button>
                    <div
                      id="interview-settings-panel"
                      className={`settings-panel ${
                        settingsOpen ? 'is-open' : ''
                      }`}
                      aria-hidden={!settingsOpen}
                    >
                      <div className="settings-panel-inner">
                        <div className="settings-title">
                          <strong>Make it yours</strong>
                          <span>
                            Customize your interview
                          </span>
                        </div>
                        <div className="settings-row">
                          <label className="settings-field">
                            Difficulty
                            <select
                              value={difficulty}
                              disabled={busy || !!pending}
                              onChange={(event) =>
                                setDifficulty(
                                  event.target.value as Difficulty
                                )
                              }
                            >
                              <option value="beginner">
                                Beginner
                              </option>
                              <option value="intermediate">
                                Intermediate
                              </option>
                              <option value="advanced">
                                Advanced
                              </option>
                            </select>
                          </label>
                          <label className="settings-field">
                            Questions
                            <input
                              type="number"
                              min={5}
                              max={5}
                              required
                              value={maxTurns}
                              disabled
                              readOnly
                              aria-label="Five questions (fixed for MVP)" 
                            />
                          </label>
                        </div>
                        <div className="settings-actions">
                          <button
                            type="button"
                            onClick={() =>
                              setSettingsOpen(false)
                            }
                          >
                            Done
                            <span aria-hidden="true">✓</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                  <span className="topic-hint">
                    {difficulty} · {maxTurns} turns
                  </span>
                </div>
                <button
                  type="submit"
                  className="start-button"
                  disabled={busy || detecting || importBusy || (!pending && (!indexed || !topic.trim()))}
                >
                  {busy
                    ? 'Preparing…'
                    : pending
                      ? 'Retry'
                      : 'Start New Interview'}
                  <span aria-hidden="true">↗</span>
                </button>
              </div>
            </form>
            <p className="welcome-note">
              Built around your code, not generic questions.
            </p>
          </div>
          {busy && (
            <p className="welcome-loading" role="status">
              Preparing your interview…
            </p>
          )}
          {error && (
            <div className="chat-error" role="alert">
              {error}
            </div>
          )}
        </section>
      ) : (
        <>
          {/* Compact interview progress */}
          <div className="conversation-info">
            <div className="conversation-title">
              <span className="repo-label">
                {current.repository_id === importState?.job?.repository_id ? importState.url.replace('https://github.com/', '') : 'Repository interview'}
              </span>
              <span className="info-divider">/</span>
              <span className="topic-label">
                {current.topic}
              </span>
            </div>
            <div className="conversation-details">
              <span>{current.difficulty}</span>
              <span>·</span>
              <span>
                {current.answered_turns} / {current.max_turns}
                  {' '}{'mastery' in current && current.mastery ? 'mastered' : 'answered'}
              </span>
              <span>·</span>
              <span>{current.status}</span>
            </div>
            <div className="progress-track">
              <div
                className="progress-fill"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
          {/* Natural document flow: no nested scroll container */}
          <section
            className="chat-messages"
            aria-label="Interview conversation"
            aria-live="polite"
          >
            {turns.map((turn, turnIndex) => (
              <div
                className="chat-turn"
                key={turn.request_id}
              >
                {turn.answer && (
                  <div className="candidate-message">
                    <div className="candidate-bubble">
                      {turn.answer}
                    </div>
                  </div>
                )}
                {turn.response.feedback && (
                  <div className="feedback-message">
                    <div className="feedback-header">
                      <span>{turn.response.feedback.evaluated === false ? 'Conversation' : 'Evaluation'}</span>
                      <span
                        className={`assessment assessment-${
                          turn.response.feedback.assessment
                        }`}
                      >
                        {
                          turn.response.feedback.evaluated === false ? 'Not scored' : turn.response.feedback.assessment
                        }
                      </span>
                    </div>
                    <p>
                      {turn.response.feedback.rationale}
                    </p>
                    {Array.isArray(
                      turn.response.feedback.missed_concepts
                    ) &&
                      turn.response.feedback.missed_concepts.length > 0 && (
                        <small>
                          Review:{' '}
                          {turn.response.feedback.missed_concepts.join(
                            ', '
                          )}
                        </small>
                      )}
                  </div>
                )}
                {turn.response.question && (turnIndex === 0 ||
                  turn.response.question !== turns[turnIndex - 1].response.question) && (
                  <div className="assistant-message">
                    <div className="assistant-name">
                      <Image
                        src="/repoiq-mascot.png"
                        alt=""
                        width={38}
                        height={38}
                        className="assistant-avatar"
                      />
                      <strong>RepoIQ</strong>
                    </div>
                    <p className="assistant-question">
                      {turn.response.question}
                    </p>
                    {!!turn.response.sources?.length && (
                      <details className="sources">
                        <summary>
                          View code references
                        </summary>
                        <Sources sources={turn.response.sources} />
                      </details>
                    )}
                  </div>
                )}
              </div>
            ))}
            {busy && (
              <div className="thinking" role="status">
                <div
                  className="thinking-dots"
                  aria-hidden="true"
                >
                  <span />
                  <span />
                  <span />
                </div>
                <span>RepoIQ is thinking…</span>
              </div>
            )}
            {current.status === 'finished' && (
              <section className="completed">
                <h2>Interview complete.</h2>
                <p>Your answers have been saved.</p>
                {!!answer && <div className="chat-error"><p>This draft was not submitted because the interview finished. Copy it before starting a new interview.</p><pre style={{ whiteSpace: 'pre-wrap' }}>{answer}</pre></div>}
                {report ? (
                  <div className="report-container">
                    <InterviewReport report={report} />
                  </div>
                ) : (
                  <button
                    type="button"
                    className="report-button"
                    onClick={() =>
                      void fetchReport(current.session_id)
                    }
                  >
                    View final report
                  </button>
                )}
              </section>
            )}
            {error && (
              <div className="chat-error" role="alert">
                <p>{error}</p>
                <button
                  type="button"
                  onClick={() => {
                    void loadSession(current.session_id)
                      .then(() => setError(''))
                      .catch((err) =>
                        setError(
                          err instanceof Error
                            ? err.message
                            : 'Unable to reload.'
                        )
                      );
                  }}
                >
                  Reload conversation
                </button>
              </div>
            )}
            <div ref={bottomRef} />
          </section>
          {/* Sticky but no independent scrolling */}
          {current.status === 'active' && (
            <form
              className="answer-area"
              onSubmit={(event) => {
                event.preventDefault();
                sendAnswer();
              }}
            >
              <div className="answer-composer">
                <label
                  htmlFor="answer"
                  className="sr-only"
                >
                  Your answer
                </label>
                <textarea
                  id="answer"
                  rows={3}
                  value={answer}
                  maxLength={6000}
                  disabled={busy}
                  placeholder="Write your answer…"
                  onChange={(event) => {
                    const updatedAnswer = event.target.value;
                    // An unchanged retry reuses its request ID; an edited answer
                    // must get a fresh ID when sent to avoid idempotency conflicts.
                    const samePendingAnswer =
                      pending?.path === `api/interviews/${current.session_id}/answers` &&
                      pending.body.answer === updatedAnswer.trim();
                    const nextPending = samePendingAnswer ? pending : null;
                    setAnswer(updatedAnswer);
                    if (pending && !nextPending) setPending(null);
                    if (error) setError('');
                    saveSession(current.session_id, nextPending, updatedAnswer);
                  }}
                  onKeyDown={handleAnswerKey}
                />
                <div className="answer-composer-bottom">
                  <span>
                    {pending && !busy
                      ? 'Not submitted · Edit your answer or press Retry'
                      : 'Enter to send · Shift + Enter for a new line'}
                  </span>
                  <button
                    type="submit"
                    className="send-icon"
                    disabled={busy || !answer.trim()}
                    aria-label={
                      pending ? 'Retry answer' : 'Send answer'
                    }
                    title={
                      pending ? 'Retry answer' : 'Send answer'
                    }
                  >
                    <svg
                      width="21"
                      height="21"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <path d="M12 19V5M5 12l7-7 7 7" />
                    </svg>
                  </button>
                </div>
              </div>
            </form>
          )}
        </>
      )}
    </div>
  );
});
export default InterviewWorkspace;
