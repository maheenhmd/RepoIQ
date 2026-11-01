
'use client';

import { useEffect, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import Image from 'next/image';

import InterviewReport from '@/components/InterviewReport';
import { ApiError, interviewApi } from '@/lib/api';
import type {
  Difficulty,
  History,
  Interview,
  Report,
  Turn,
} from '@/types';

import './workspace.css';

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

const DEFAULT_REPO =
  'a7f04a87-1380-4a80-871f-3fddd665535f';

const DEFAULT_TOPIC =
  'HTTP authentication and error handling';

export default function InterviewPage() {
  const [current, setCurrent] = useState<Interview | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [report, setReport] = useState<Report | null>(null);

  const [repo, setRepo] = useState(DEFAULT_REPO);
  const [topic, setTopic] = useState(DEFAULT_TOPIC);
  const [difficulty, setDifficulty] =
    useState<Difficulty>('intermediate');
  const [maxTurns, setMaxTurns] = useState(4);

  const [answer, setAnswer] = useState('');
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);

  const [settingsOpen, setSettingsOpen] = useState(false);

  const lock = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);

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
    const history = await interviewApi<History>(
      `api/interviews/${sessionId}`
    );

    setCurrent(history.current);
    setTurns(history.turns);
    setReport(history.current.report ?? null);

    if (
      history.current.status === 'finished' &&
      !history.current.report
    ) {
      try {
        const result = await interviewApi<Report>(
          `api/interviews/${sessionId}/report`
        );

        setReport(result);
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
    if (!current) return;

    bottomRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    });
  }, [current, turns.length, report]);

  async function fetchReport(sessionId: string) {
    try {
      const result = await interviewApi<Report>(
        `api/interviews/${sessionId}/report`
      );

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

      setCurrent(response);
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
        ];
      });

      setAnswer('');
      setPending(null);
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

            setError(
              'Interview changed. Review the latest question before sending again.'
            );
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

    if (busy || (!topic.trim() && !pending)) return;

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
      (!pending && !answer.trim())
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
    if (
      (current || pending || answer) &&
      !window.confirm(
        'Start a new interview? Your previous interview remains saved.'
      )
    ) {
      return;
    }

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
    <main className="repoiq-chat">
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

                        <label className="settings-field">
                          Repository ID
                          <input
                            value={repo}
                            required
                            pattern="[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
                            disabled={busy || !!pending}
                            onChange={(event) =>
                              setRepo(event.target.value)
                            }
                          />
                        </label>

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
                              min={1}
                              max={20}
                              required
                              value={maxTurns}
                              disabled={busy || !!pending}
                              onChange={(event) =>
                                setMaxTurns(
                                  Number(event.target.value)
                                )
                              }
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
                  disabled={busy || !topic.trim()}
                >
                  {busy
                    ? 'Preparing…'
                    : pending
                      ? 'Retry'
                      : 'Start interview'}

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
                {current.repository_id === DEFAULT_REPO
                  ? 'psf / requests'
                  : 'Repository interview'}
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
                {' '}answered
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
            {turns.map((turn) => (
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
                      <span>Evaluation</span>

                      <span
                        className={`assessment assessment-${
                          turn.response.feedback.assessment
                        }`}
                      >
                        {
                          turn.response.feedback.assessment
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

                {turn.response.question && (
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

                        <ul>
                          {turn.response.sources.map(
                            (source) => (
                              <li key={source.source_id}>
                                <code>
                                  {source.file_path}:
                                  {source.start_line}–
                                  {source.end_line}
                                </code>

                                {source.symbol_name &&
                                  ` · ${source.symbol_name}`}
                              </li>
                            )
                          )}
                        </ul>
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
                  disabled={busy || !!pending}
                  placeholder="Write your answer…"
                  onChange={(event) => {
                    setAnswer(event.target.value);

                    saveSession(
                      current.session_id,
                      pending,
                      event.target.value
                    );
                  }}
                  onKeyDown={handleAnswerKey}
                />

                <div className="answer-composer-bottom">
                  <span>
                    Enter to send · Shift + Enter for a new line
                  </span>

                  <button
                    type="submit"
                    className="send-icon"
                    disabled={
                      busy ||
                      (!pending && !answer.trim())
                    }
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
    </main>
  );
}
