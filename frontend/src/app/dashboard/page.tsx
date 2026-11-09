'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import Sidebar from '@/components/dashboard/Sidebar';
import RepositoryChat from '@/components/RepositoryChat';
import InterviewWorkspace from '@/components/interview/InterviewWorkspace';
import type { WorkspaceHandle } from '@/components/interview/InterviewWorkspace';
import type { Interview } from '@/types';
import { lookupRepository, lookupInterviews, deleteInterview } from '@/lib/api';
import type { SavedInterview } from '@/lib/api';
import styles from '@/styles/dashboard/dashboard.module.css';

function canonical(raw: string) {
  const url = new URL(raw.trim());
  if (url.protocol !== 'https:' || url.hostname !== 'github.com' || url.port || url.username || url.password || url.search || url.hash || !/^\/[a-z0-9-]{1,39}\/[a-z0-9_.-]{1,100}\/?$/i.test(url.pathname)) throw Error('Use https://github.com/owner/repository');
  return 'https://github.com' + url.pathname.replace(/\/$/, '').replace(/\.git$/i, '').toLowerCase();
}
export default function DashboardPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true), [mobileOpen, setMobileOpen] = useState(false);
  const [view, setView] = useState('interviewer');
  const [recent, setRecent] = useState<string[]>([]);
  const [url, setUrl] = useState(''), [input, setInput] = useState('');
  const [repositoryId, setRepositoryId] = useState('');
  const [session, setSession] = useState<Interview | null>(null);
  const [busy, setBusy] = useState(true), [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<SavedInterview[]>([]);
  const [error, setError] = useState(''), [status, setStatus] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [deleting, setDeleting] = useState<string | null>(null);
  const deletionLock = useRef(false);
  async function removeInterview(item: SavedInterview) {
    if (busy || deletionLock.current) return;
    if (!window.confirm(`Permanently delete “${item.topic}” and all its answers, history and report? This cannot be undone.`)) return;
    deletionLock.current = true; setDeleting(item.session_id); setError('');
    try {
      await deleteInterview(item.session_id);
      workspace.current?.forgetSession(item.session_id);
      setHistory(previous => previous.filter(row => row.session_id !== item.session_id));
      if (session?.session_id === item.session_id) setSession(null);
      setRefresh(value => value + 1);
    } catch (error) { setError(error instanceof Error ? error.message : 'Could not delete interview. Please retry.'); }
    finally { deletionLock.current = false; setDeleting(null); }
  }
  const workspace = useRef<WorkspaceHandle>(null), selection = useRef(0);
  useEffect(() => { try {
    const values: unknown = JSON.parse(localStorage.getItem('repoiq-recent-repositories') ?? '[]');
    if (Array.isArray(values)) setRecent([...new Set(values.filter((v): v is string => typeof v === 'string').flatMap(v => { try { return [canonical(v)]; } catch { return []; } }))].slice(0,20));
  } catch {} }, []);
  const remember = useCallback((raw: string) => { try {
    const normalized = canonical(raw);
    setRecent(previous => {
      const next = [normalized, ...previous.filter(v => v !== normalized)].slice(0,20);
      try { localStorage.setItem('repoiq-recent-repositories', JSON.stringify(next)); } catch {}
      return next;
    }); setUrl(normalized);
  } catch {} }, []);
  const updated = useCallback((value: { session: Interview | null; repositoryId: string; url: string; busy: boolean }) => {
    setSession(value.session); setRepositoryId(value.repositoryId); setBusy(value.busy);
    if (value.url) remember(value.url);
  }, [remember]);
  useEffect(() => {
    if (!repositoryId) { setHistory([]); return; }
    let cancelled = false; setLoading(true); setError('');
    lookupInterviews(repositoryId).then(rows => { if (!cancelled) setHistory([...rows].sort((a,b) => b.updated_at.localeCompare(a.updated_at))); })
      .catch(e => { if (!cancelled) { setHistory([]); setError(e.message); } }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [repositoryId, session?.version, session?.session_id, refresh]);
  function navigate(next: string) {
    if (deletionLock.current) return;
    if (next === 'new') { if (busy) return; workspace.current?.newInterview(); setView('interviewer'); }
    else setView(next);
    setMobileOpen(false);
  }
  async function choose(raw: string) {
    if (busy || deletionLock.current) return;
    let normalized: string; try { normalized = canonical(raw); } catch(e) { setError((e as Error).message); return; }
    const version = ++selection.current; setLoading(true); setError('');
    try {
      const result = await lookupRepository(normalized); if (version !== selection.current) return;
      setStatus(result.indexing_complete ? 'Indexed and ready. Open in AI Interviewer; no import needed.' : result.repository_id ? 'Repository found; open AI Interviewer to monitor indexing.' : 'Not indexed. Open AI Interviewer to import this repository.');
      remember(normalized); workspace.current?.selectRepository(normalized); setView('interviewer'); setMobileOpen(false);
    } catch(e) { if (version === selection.current) setError((e as Error).message); }
    finally { if (version === selection.current) setLoading(false); }
  }
  function open(id: string) { if (busy || deletionLock.current) return; workspace.current?.openSession(id); setView('interviewer'); setMobileOpen(false); }
  return <main className={styles.dashboard} onKeyDown={e => { if (e.key === 'Escape') setMobileOpen(false); }}>
    {mobileOpen && <button className={styles.overlay} onClick={() => setMobileOpen(false)} aria-label="Close sidebar" />}
    <div className={[styles.sidebarContainer, !sidebarOpen ? styles.sidebarCollapsed : '', mobileOpen ? styles.sidebarMobileOpen : ''].join(' ')}>
      <Sidebar collapsed={!sidebarOpen} mobileOpen={mobileOpen} onToggle={() => setSidebarOpen(v => !v)} onClose={() => setMobileOpen(false)} view={view} onNavigate={navigate} sessions={history} repositories={recent} selectedUrl={url} activeSession={session?.session_id} disabled={busy || loading} onSession={open} onRepository={choose} loading={loading} />
    </div>
    <section className={styles.mainPanel} inert={mobileOpen}>
      <header className={styles.topbar}><div className={styles.topbarLeft}>
        <button className={styles.mobileMenu} aria-label="Open sidebar" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}>☰</button>
        {!sidebarOpen && <button className={styles.desktopMenu} aria-label="Expand sidebar" onClick={() => setSidebarOpen(true)}>☰</button>}
        <div className={styles.pageIdentity}><span className={styles.pageTitle}>Repo<span>IQ</span></span><span className={styles.pageSubtitle}>{view === 'history' ? 'Interview History' : view === 'repositories' ? 'My Repositories' : 'AI Interviewer'}</span></div>
      </div><span className={styles.status}>Local workspace</span></header>
      <div className={styles.chatArea}>
        {error && <p role="alert" className={styles.notice}>{error} <button onClick={() => setRefresh(n => n+1)}>Retry history</button></p>}
        <div hidden={view !== 'interviewer'}><InterviewWorkspace ref={workspace} embedded onUpdate={updated} /></div>
        <div hidden={view !== 'chat'}>{repositoryId ? <RepositoryChat key={repositoryId} repositoryId={repositoryId} active={view === 'chat'} /> : <section className={styles.panel}><h1>Chat with Repository</h1><p>Select an indexed repository first. You do not need to start an interview.</p><button onClick={() => setView('repositories')}>Choose repository</button></section>}</div>
        {view === 'repositories' && <section className={styles.panel}><h1>My Repositories</h1><p>Recently used in this browser. Indexed state is checked in PostgreSQL.</p>
          <form onSubmit={e => { e.preventDefault(); void choose(input); }}><label htmlFor="repository-url">Public GitHub URL</label><div className={styles.panelControls}><input id="repository-url" type="url" required value={input} onChange={e => setInput(e.target.value)} placeholder="https://github.com/owner/repository" /><button disabled={busy || loading}>Check & open</button></div></form>
          <p role="status">{loading ? 'Checking…' : status}</p>
          {!recent.length && <p>No recent repositories yet. Enter a URL to get started.</p>}
          {recent.map(repo => <button className={styles.listItem} disabled={busy || loading} key={repo} onClick={() => void choose(repo)}><strong>{repo.replace('https://github.com/','')}</strong><span>Check status & open ↗</span></button>)}
        </section>}
        {view === 'history' && <section className={styles.panel}><h1>Interview History</h1><p>{url || 'Select a repository first.'}</p><p>History is shared by repository; account ownership is not implemented.</p>
          <button onClick={() => setRefresh(n => n+1)} disabled={loading}>Refresh history</button>
          {loading ? <p role="status">Loading saved conversations…</p> : !history.length ? <p>No saved interviews for the selected repository.</p> : history.map(item => <div key={item.session_id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button className={styles.listItem} disabled={busy || !!deleting} onClick={() => open(item.session_id)}><strong>{item.topic}</strong><span>{item.status === 'finished' ? 'View report' : 'Resume'} · {new Date(item.updated_at).toLocaleString()}</span></button>
            <button type="button" disabled={busy || !!deleting} onClick={() => void removeInterview(item)} aria-label={`Delete interview: ${item.topic}`} title="Delete interview" style={{ border: '1px solid #61413c', borderRadius: 8, background: '#352627', color: '#ffad9d', padding: 10, cursor: 'pointer' }}>
              {deleting === item.session_id ? 'Deleting…' : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7" /></svg>}
            </button>
          </div>)}
        </section>}
      </div>
    </section>
  </main>;
}

