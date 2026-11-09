'use client';
import Image from 'next/image';
import Link from 'next/link';
import type { SavedInterview } from '@/lib/api';
import styles from '@/styles/dashboard/dashboard.module.css';
type Props = { collapsed: boolean; mobileOpen: boolean; onToggle: () => void; onClose: () => void; view: string; onNavigate: (view: string) => void; sessions: SavedInterview[]; repositories: string[]; selectedUrl: string; activeSession?: string; disabled: boolean; loading: boolean; onSession: (id: string) => void; onRepository: (url: string) => void };
export default function Sidebar(p: Props) {
  const compact = p.collapsed && !p.mobileOpen;
  return <aside className={styles.sidebar} aria-label="Workspace sidebar">
    <div className={styles.sidebarHeader}><Link href="/" className={styles.brand} aria-label="RepoIQ home"><Image src="/repoiq-mascot.png" alt="" width={36} height={36} className={styles.brandLogo} />{!compact && <span className={styles.brandName}>Repo<span>IQ</span></span>}</Link><button className={styles.collapseButton} onClick={p.mobileOpen ? p.onClose : p.onToggle} aria-label={p.mobileOpen ? 'Close sidebar' : 'Collapse sidebar'}>☰</button></div>
    <div className={styles.sidebarContent}><button disabled={p.disabled} className={styles.newInterview} onClick={() => p.onNavigate('new')} title="New Interview"><span className={styles.plusIcon}>+</span>{!compact && 'New Interview'}</button>
      <nav className={styles.navigation} aria-label="Workspace navigation">{[['interviewer','◇','AI Interviewer'],['chat','◌','Chat with Repository'],['repositories','▤','My Repositories'],['history','◷','Interview History']].map(([view,icon,label]) => <button key={view} title={label} className={styles.navItem + (p.view === view ? ' '+styles.navActive : '')} aria-current={p.view === view ? 'page' : undefined} onClick={() => p.onNavigate(view)}><span className={styles.navIcon}>{icon}</span>{!compact && label}</button>)}</nav>
      {!compact && <><section className={styles.recentSection}><h2 className={styles.sectionHeading}>RECENT CONVERSATIONS</h2>
        {p.loading ? <p className={styles.emptyHistory}>Loading…</p> : !p.sessions.length ? <p className={styles.emptyHistory}>Select a repository to see saved interviews.</p> : p.sessions.slice(0,10).map(item => <button key={item.session_id} disabled={p.disabled} className={styles.listItem + (p.activeSession === item.session_id ? ' '+styles.navActive : '')} onClick={() => p.onSession(item.session_id)}><strong>{item.topic}</strong><small>{item.status === 'finished' ? 'Completed' : 'Active'} · {new Date(item.updated_at).toLocaleDateString()}</small></button>)}
      </section><section className={styles.recentSection}><h2 className={styles.sectionHeading}>RECENT REPOSITORIES</h2>{!p.repositories.length && <p className={styles.emptyHistory}>Repositories used in this browser appear here.</p>}{p.repositories.slice(0,10).map(url => <button key={url} disabled={p.disabled} className={styles.listItem + (url === p.selectedUrl ? ' '+styles.navActive : '')} onClick={() => p.onRepository(url)}>{url.replace('https://github.com/','')}</button>)}</section></>}
    </div><footer className={styles.sidebarFooter}>{!compact && <p className={styles.emptyHistory}>Local workspace · no account connected</p>}</footer>
  </aside>;
}

