import type { Report } from '@/types';
import { Sources } from './QuestionCard';
export default function InterviewReport({ report }: { report: Report }) {
  return <section className="report"><span className="eyebrow">YOUR INTERVIEW, REFLECTED</span>
    <h2>Good practice. Clear next steps.</h2><div className="score">{report.overall_score ?? '—'}<small> / 100 · practice score</small></div>
    <p>{report.summary}</p><p>{Object.entries(report.assessment_counts).map(([name, count]) => `${count} ${name}`).join(' · ')}</p>
    <div className="table-wrap"><table><thead><tr><th>Topic</th><th>Correctness</th><th>Depth</th></tr></thead><tbody>{report.topics.map(topic => <tr key={topic.topic}><td>{topic.topic}</td><td>{topic.correctness_score}/100</td><td>{topic.depth_score === null ? 'Unassessed' : `${topic.depth_score}/100`}</td></tr>)}</tbody></table></div>
    {(['strengths', 'weaknesses', 'recommendations'] as const).map(key => <section key={key}><h3>{key}</h3>{report[key].length ? <ul>{report[key].map((value, i) => <li key={i}>{value}</li>)}</ul> : <p>No recorded findings.</p>}</section>)}
    <details><summary>Scoring & supporting evidence</summary><p>{report.score_explanation}</p>{report.evaluations.map(item => <div key={item.turn}><h4>Answer {item.turn}</h4><Sources sources={item.sources} /></div>)}</details>
  </section>;
}
