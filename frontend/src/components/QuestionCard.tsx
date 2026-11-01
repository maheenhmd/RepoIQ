import type { Source } from '@/types';

export function Sources({ sources }: { sources: Source[] }) {
  return <div className="sources">{sources.map(source => <details key={`${source.chunk_id}-${source.start_line}`}>
    <summary>{source.file_path} · L{source.start_line}–{source.end_line}</summary>
    <small>{source.symbol_name} · commit {source.commit_sha.slice(0, 8)}</small>
    <pre><code>{source.content}</code></pre>
  </details>)}</div>;
}
export default function QuestionCard({ question, sources }: { question: string; sources: Source[] }) {
  return <section className="question"><span className="eyebrow">REPOIQ / INTERVIEWER</span>
    <h2>{question}</h2><Sources sources={sources} /></section>;
}
