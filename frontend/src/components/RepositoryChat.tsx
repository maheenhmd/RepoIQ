'use client';
import { createElement, memo, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { frameBuffer, prependScrollTop, shouldFollow } from '@/lib/chat-display';
import { ApiError, interviewApi, streamChat } from '@/lib/api';
import { Sources } from './QuestionCard';
import type { Source } from '@/types';
import { browserVoiceIO, VoiceConversation, type VoiceState } from '@/lib/voice';
import styles from './RepositoryChat.module.css';

type Reply = { chat_id: string; repository_id: string; version: number; answer: string; sources: Source[]; mode?: 'repository' | 'general' | 'general_fallback' | 'casual' };
type Turn = { request_id: string; message: string; response: Reply };
type History = { chat_id: string; repository_id: string; version: number; turns: Turn[]; has_older: boolean };
type Pending = { request_id: string; expected_version: number; message: string };

// Deliberately render a safe Markdown subset as React text; never accept raw HTML.
function inline(text: string) {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((part, key) => part.startsWith('`')
    ? <code key={key}>{part.slice(1, -1)}</code> : part.startsWith('**')
    ? <strong key={key}>{part.slice(2, -2)}</strong> : part);
}

const MarkdownBlock = memo(function MarkdownBlock({ block }: { block: string }) {
  if (block.startsWith('```')) return <pre><code>{block.replace(/^```[^\n]*\n?/, '').replace(/```$/, '')}</code></pre>;
  const lines = block.split('\n'), nodes = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i], heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (!line.trim()) continue;
    if (heading) { nodes.push(createElement(`h${heading[1].length}`, { key: i }, inline(heading[2]))); continue; }
    const list = line.match(/^\s*(?:([-*+])|\d+\.)\s+(.+)$/);
    if (list) {
      const start = i, ordered = !list[1], items = [];
      for (; i < lines.length; i++) {
        const item = lines[i].match(ordered ? /^\s*\d+\.\s+(.+)$/ : /^\s*[-*+]\s+(.+)$/);
        if (!item) break;
        items.push(<li key={i}>{inline(item[1])}</li>);
      }
      i--;
      nodes.push(ordered ? <ol key={start}>{items}</ol> : <ul key={start}>{items}</ul>);
    } else if (line.startsWith('> ')) nodes.push(<blockquote key={i}>{inline(line.slice(2))}</blockquote>);
    else nodes.push(<p key={i}>{inline(line)}</p>);
  }
  return <>{nodes}</>;
});

const Markdown = memo(function Markdown({ text }: { text: string }) {
  return <>{text.split(/(```[\s\S]*?(?:```|$))/g).map((block, i) => <MarkdownBlock key={i} block={block} />)}</>;
});

const SavedTurn = memo(function SavedTurn({ turn }: { turn: Turn }) {
  return <article><div className={styles.user}>{turn.message}</div><div className={styles.assistant}><strong>RepoIQ</strong>{turn.response.mode === 'general' && <small> · General programming knowledge</small>}<Markdown text={turn.response.answer} /><Sources sources={turn.response.sources} /></div></article>;
});

export default function RepositoryChat({ repositoryId, active = true }: { repositoryId: string; active?: boolean }) {
  const key = 'repoiq-chat-' + repositoryId;
  const [chatId, setChatId] = useState(''), [version, setVersion] = useState(0);
  const [turns, setTurns] = useState<Turn[]>([]), [draft, setDraft] = useState('');
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(true), [older, setOlder] = useState(false), [error, setError] = useState('');
  const lock = useRef(false), conversation = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const follow = useRef(true), lastTop = useRef(0);
  const prepend = useRef<{ height: number; top: number } | null>(null);
  const buffer = useRef<ReturnType<typeof frameBuffer> | null>(null);
  const mounted = useRef(true);
  const [following, setFollowing] = useState(true);
  const voice = useRef<VoiceConversation | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceState>('off');
  const [voiceSupported, setVoiceSupported] = useState(false), [transcript, setTranscript] = useState('');
  const [language, setLanguage] = useState('en-US');
  const streamAbort = useRef<AbortController | null>(null);
  const created = useRef(false);
  const [streamText, setStreamText] = useState(''), [streamStage, setStreamStage] = useState('loading');
  function save(id: string, message: string, request: Pending | null) {
    try { localStorage.setItem(key, JSON.stringify({ id, message, request })); }
    catch { setError('Browser storage unavailable; keep this chat open.'); }
  }
  async function history(id: string) {
    const result = await interviewApi<History>(`api/chats/${repositoryId}/${id}`);
    if (result.repository_id !== repositoryId) throw Error('Repository mismatch');
    if (!mounted.current) return result;
    created.current = true;
    setChatId(id); setVersion(result.version); setTurns(result.turns); setOlder(result.has_older);
    return result;
  }
  useEffect(() => {
    let live = true;
    async function restore() {
      try {
        const saved = JSON.parse(localStorage.getItem(key) ?? 'null');
        if (!saved || !live) return;
        setChatId(saved.id ?? ''); setDraft(saved.message ?? ''); setPending(saved.request ?? null);
        if (saved.id) {
          try {
            const result = await history(saved.id);
            if (!live) return;
            if (saved.request && result.turns.some(turn => turn.request_id === saved.request.request_id)) {
              setDraft(''); setPending(null); save(saved.id, '', null);
            }
          } catch (e) { if (!(e instanceof ApiError && e.status === 404 && saved.request)) throw e; }
        }
      } catch(e) { if (live) setError((e as Error).message); }
      finally { if (live) setBusy(false); }
    }
    void restore(); return () => { live = false; };
  }, [key]);
  useLayoutEffect(() => {
    const node = conversation.current;
    if (!node || !active) return;
    if (prepend.current) {
      node.scrollTop = prependScrollTop(prepend.current.top, prepend.current.height, node.scrollHeight);
      prepend.current = null;
    } else if (follow.current) node.scrollTop = node.scrollHeight;
    lastTop.current = node.scrollTop;
  }, [turns, busy, streamText, error, active]);
  useLayoutEffect(() => {
    if (composer.current) {
      composer.current.style.height = 'auto';
      composer.current.style.height = `${Math.min(composer.current.scrollHeight, 160)}px`;
    }
  }, [draft, active]);
  useEffect(() => {
    const node = conversation.current;
    if (!node || !active) return;
    const observer = new ResizeObserver(() => {
      if (follow.current) { node.scrollTop = node.scrollHeight; lastTop.current = node.scrollTop; }
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [active]);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; buffer.current?.close(); streamAbort.current?.abort(); };
  }, []);
  async function send(spoken?: string): Promise<string | undefined> {
    if (busy || lock.current || (!(spoken ?? draft).trim() && !pending)) return;
    lock.current = true; setBusy(true); setError('');
    setStreamText(''); setStreamStage('retrieving');
    const controller = new AbortController(); streamAbort.current = controller;
    const display = frameBuffer(setStreamText); buffer.current = display;
    const id = chatId || crypto.randomUUID();
    const message = spoken ?? draft;
    const retrying = !!pending;
    if (spoken) setDraft(spoken);
    const request = pending ?? { request_id: crypto.randomUUID(), expected_version: version, message: message.trim() };
    setChatId(id); setPending(request); save(id, message, request);
    try {
      // Idempotent creation also recovers an interrupted first-send response.
      if (!created.current) {
        await interviewApi<History>('api/chats', { repository_id: repositoryId, request_id: id });
        created.current = true;
      }
      controller.signal.throwIfAborted();
      const reply = await streamChat<Reply>(`api/chats/${repositoryId}/${id}/messages/stream`, request,
        display.append, stage => { if (mounted.current && !controller.signal.aborted) setStreamStage(stage); }, controller.signal);
      display.close();
      if (!mounted.current) return;
      // Show the committed response immediately, even if the history refresh fails.
      setTurns(previous => previous.some(turn => turn.request_id === request.request_id) ? previous :
        [...previous, { request_id: request.request_id, message: request.message, response: reply }]);
      setVersion(reply.version);
      setStreamText('');
      setDraft(''); setPending(null); save(id, '', null);
      if (retrying) {
        try { await history(id); }
        catch { setError('Answer saved. Older history could not refresh; reload to try again.'); }
      }
      return reply.answer;
    } catch(e) {
      display.close(mounted.current);
      if (!mounted.current) return;
      setError((e as Error).message);
      if (e instanceof ApiError && e.status === 429) {
        setError('AI is still processing another request. Your draft is saved. Wait for completion, then retry this same message.');
      }
      if (e instanceof ApiError && e.status === 409) {
        try {
          const result = await history(id);
          const applied = result.turns.some(turn => turn.request_id === request.request_id);
          setPending(null); if (applied) { setDraft(''); setError(''); }
          save(id, applied ? '' : message, null);
        } catch { /* Original UUID remains available for retry. */ }
      } else if (e instanceof ApiError && e.status === 422) { setPending(null); save(id, message, null); }
    } finally { display.close(); buffer.current = null; streamAbort.current = null; lock.current = false; if (mounted.current) setBusy(false); }
  }
  const voiceSend = useRef(send), voiceTranscript = useRef((text: string) => { setTranscript(text); });
  voiceSend.current = send;
  voiceTranscript.current = text => {
    setTranscript(text);
    if (text) { setDraft(text); save(chatId, text, null); }
  };
  useEffect(() => {
    const io = browserVoiceIO(); setVoiceSupported(!!io);
    if (!io) return;
    const controller = new VoiceConversation(io, async text => {
      const result = await voiceSend.current(text);
      if (!result) throw Error('Message not committed');
      return result;
    }, setVoiceState, text => voiceTranscript.current(text), setError);
    voice.current = controller;
    const visibility = () => { if (document.hidden) controller.stop(); };
    document.addEventListener('visibilitychange', visibility);
    return () => { controller.stop(); voice.current = null; document.removeEventListener('visibilitychange', visibility); };
  }, []);
  useEffect(() => { if (!active) voice.current?.stop(); }, [active]);
  return <section className={styles.chat} aria-label="Chat with Repository">
    <header><div><span>REPOSITORY ASSISTANT</span><h1>Chat with your code.</h1><p>Explain, explore, or plan changes. Facts come with evidence; proposals are suggestions.</p></div><button disabled={busy || voiceState !== 'off'} onClick={() => {
      if (draft && !window.confirm('Start a new chat and leave this draft?')) return;
      created.current = false; setStreamText(''); follow.current = true; setFollowing(true);
      setChatId(''); setVersion(0); setTurns([]); setDraft(''); setPending(null); setOlder(false); setError(''); save('', '', null);
    }}>＋ New Chat</button></header>
   
<details className={styles.voicePanel}>
  <summary className={styles.voiceSummary}>
    <span className={styles.voiceSummaryIcon}>
      <svg
        width="19"
        height="19"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <rect x="9" y="2" width="6" height="13" rx="3" />
        <path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8" />
      </svg>
    </span>

    <span className={styles.voiceSummaryText}>
      <span className={styles.voiceSummaryTitle}>
        Voice Assistant
      </span>
      <span className={styles.voiceSummaryDescription}>
        Talk naturally with your repository
      </span>
    </span>

    <span
      className={`${styles.voiceStatus} ${
        voiceState !== 'off' ? styles.voiceStatusActive : ''
      }`}
      role="status"
    >
      <span className={styles.voiceStatusDot} />
      {voiceState === 'off'
        ? 'Inactive'
        : voiceState.charAt(0).toUpperCase() +
          voiceState.slice(1)}
    </span>

    <svg
      className={styles.voiceChevron}
      width="18"
      height="18"
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
  </summary>

  <div className={styles.voice}>
    <div className={styles.voiceIntro}>
      <div>
        <h3>Voice conversation</h3>
        <p>
          Ask questions about your code without typing.
        </p>
      </div>
    </div>

    <div className={styles.voiceControls}>
      <button
        type="button"
        className={`${styles.voiceButton} ${
          voiceState !== 'off' ? styles.voiceButtonActive : ''
        }`}
        aria-pressed={voiceState !== 'off'}
        disabled={
          voiceState === 'off' &&
          (!voiceSupported || busy || !!pending || !!draft.trim())
        }
        onClick={() => {
          if (voiceState === 'off') {
            voice.current?.start(language);
          } else {
            voice.current?.stop();
          }
        }}
      >
        {voiceState === 'off' ? (
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="9" y="2" width="6" height="13" rx="3" />
            <path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8" />
          </svg>
        ) : (
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="currentColor"
            aria-hidden="true"
          >
            <rect x="5" y="5" width="14" height="14" rx="3" />
          </svg>
        )}

        <span>
          {voiceState === 'off'
            ? 'Start conversation'
            : 'End conversation'}
        </span>
      </button>

      <label className={styles.voiceSelectWrap}>
        <span>Speech language</span>
        <select
          className={styles.voiceSelect}
          value={language}
          disabled={voiceState !== 'off'}
          onChange={e => setLanguage(e.target.value)}
        >
          <option value="en-US">English</option>
          <option value="ur-PK">Urdu</option>
        </select>
      </label>
    </div>

    {voiceState !== 'off' && (
      <div className={styles.voiceActivity} role="status">
        <span className={styles.voiceActivityDot} />
        <span>
          {voiceState.charAt(0).toUpperCase() +
            voiceState.slice(1)}
        </span>
      </div>
    )}

    {transcript && (
      <div className={styles.voiceTranscript}>
        <div className={styles.voiceTranscriptHeader}>
          <span className={styles.voiceTranscriptDot} />
          <span>Live transcript</span>
        </div>
        <p>{transcript}</p>
      </div>
    )}

    <div className={styles.voiceFooter}>
      <svg
        width="15"
        height="15"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v5m0-8h.01" />
      </svg>
      <span>
        {voiceSupported
          ? 'Uses browser speech services. RepoIQ does not store audio. Clear your text draft before starting.'
          : 'Voice requires a supported browser, microphone permission, and HTTPS or localhost.'}
      </span>
    </div>
  </div>
</details>

    <div ref={conversation} className={styles.conversation} role="region" aria-label="Conversation" tabIndex={0} onScroll={e => {
      const node = e.currentTarget;
      follow.current = shouldFollow(node.scrollTop, lastTop.current, node.scrollHeight, node.clientHeight);
      lastTop.current = node.scrollTop; setFollowing(follow.current);
    }}>
    {older && <button disabled={busy} onClick={async () => { setBusy(true); setStreamStage('loading'); try {
      const page = await interviewApi<History>(`api/chats/${repositoryId}/${chatId}?before=${turns[0].response.version}`);
      if (conversation.current) prepend.current = { height: conversation.current.scrollHeight, top: conversation.current.scrollTop };
      setTurns(previous => [...page.turns, ...previous]); setOlder(page.has_older);
    } catch(e) { setError((e as Error).message); } finally { setBusy(false); } }}>Load older messages</button>}
    {!turns.length && !pending && !busy && <div className={styles.empty}><h2>Understand the project before the interview.</h2><p>Try “Explain how this project works” or name a function you want to explore.</p></div>}
    <div>{turns.map(turn => <SavedTurn key={turn.request_id} turn={turn} />)}</div>
    {pending && !turns.some(turn => turn.request_id === pending.request_id) && <article><div className={styles.user}>{pending.message}</div><div className={styles.assistant} aria-busy={busy}>
      <strong>RepoIQ · {busy ? 'Typing' : 'Interrupted'}</strong><small> Provisional text · not saved or citation-verified yet</small>
      <Markdown text={streamText} />
    </div></article>}
    {busy && <p role="status">{streamStage === 'loading' ? 'Loading messages…' : streamStage === 'generating' ? 'AI is responding…' : 'Finding relevant code…'} {streamAbort.current && <button type="button" onClick={() => { voice.current?.stop(); buffer.current?.close(true); streamAbort.current?.abort(); }}>Stop response</button>}</p>}
    {error && <p role="alert" className={styles.error}>{error}</p>}
    </div>
    {!following && <button className={styles.jump} type="button" onClick={() => {
      follow.current = true; setFollowing(true);
      if (conversation.current) { conversation.current.scrollTop = conversation.current.scrollHeight; lastTop.current = conversation.current.scrollTop; }
    }}>Jump to latest ↓</button>}
    <form onSubmit={e => { e.preventDefault(); if (voiceState === 'off') void send(); }}><label htmlFor="repository-chat-message">Ask about this repository</label><textarea ref={composer} rows={1} id="repository-chat-message" maxLength={4000} value={draft} disabled={busy || !!pending || voiceState !== 'off'} onChange={e => { setDraft(e.target.value); save(chatId, e.target.value, null); }} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} placeholder="Ask a question, or follow up with “why?”…" /><div><small>Enter to send · Shift+Enter for a new line</small><button disabled={busy || voiceState !== 'off' || (!pending && !draft.trim())}>{pending ? 'Retry message' : 'Send'} ↗</button></div></form>
  </section>;
}
