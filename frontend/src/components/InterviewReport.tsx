'use client';
import type { Report } from '@/types';
import { Sources } from './QuestionCard';

export default function InterviewReport({ report }: { report: Report }) {
  const score = report.overall_score;
  const valid = score !== null && Number.isFinite(score) && score >= 0 && score <= 100;
  const value = valid ? score! : 0;
  const celebration = valid && value >= 85;
  const message = !valid ? 'Your practice, reflected.' : celebration ? 'Strong work. Keep exploring.' : value >= 65 ? 'You’re building real understanding.' : 'Every attempt is a step forward.';
  return <section className="iq-report" aria-label="Interview performance report">
    <div className="report-intro"><span className="report-kicker">PRACTICE / REFLECTION / PROGRESS</span><h2>{message}</h2><p>{report.summary}</p></div>
    {celebration && <div className="report-confetti" aria-hidden="true">🎉 <i>▪</i> <i>◆</i> <i>▪</i> <i>◆</i></div>}
    {valid && value >= 65 && value < 85 && <p aria-hidden="true">✨ A thoughtful foundation to build on.</p>}
    <div className="report-overview"><div className="report-ring" role="img" aria-label={valid ? `Practice score ${score} out of 100` : 'Score unavailable'}>
      <svg viewBox="0 0 120 120" aria-hidden="true"><circle className="ring-track" cx="60" cy="60" r="52" /><circle className="ring-value" cx="60" cy="60" r="52" pathLength="100" strokeDasharray={`${value} 100`} /></svg>
      <div><strong>{valid ? score : '—'}</strong><span>out of 100</span></div></div>
      <div><h3>What your answers demonstrated</h3><p>AI-generated practice feedback, not a hiring assessment.</p><div className="assessment-list">{Object.entries(report.assessment_counts).map(([label, count]) => <span key={label}><b>{count}</b> {label}</span>)}</div></div></div>
    <section><h3>Topic breakdown</h3>{report.topics.map((topic, index) => <div className="topic-performance" key={`${topic.topic}-${index}`}><div><strong>{topic.topic}</strong><span>{topic.correctness_score}/100</span></div><progress value={topic.correctness_score} max={100} aria-label={`${topic.topic} correctness`} /><small>Depth: {topic.depth_score === null ? 'Not assessed' : `${topic.depth_score}/100`}</small></div>)}</section>
    <div className="report-findings">{(['strengths', 'weaknesses', 'recommendations'] as const).map(key => <section key={key}><h3>{key === 'weaknesses' ? 'Room to grow' : key === 'recommendations' ? 'Your next steps' : 'Strengths'}</h3>{report[key].length ? <ul>{report[key].map((text, index) => <li key={index}>{text}</li>)}</ul> : <p>No recorded findings.</p>}</section>)}</div>
    <details className="report-evidence"><summary>Explore the evidence & scoring rubric</summary><p>{report.score_explanation}</p>{report.evaluations.map(item => <div key={item.turn}><h4>Answer {item.turn}</h4><Sources sources={item.sources} /></div>)}</details>
    <div className="report-actions"><a href="/interview?new=1">Start New Interview ↗</a><button type="button" onClick={() => window.print()}>Print / save report</button></div>
    <style jsx>{`
      .iq-report{position:relative;overflow:hidden;background:#202125;color:#f7f7f8;border:1px solid #41434a;border-radius:24px;padding:clamp(20px,4vw,44px);line-height:1.65}
      .report-kicker{font-size:10px;letter-spacing:2px;color:#35d8c7}.report-intro h2{font-size:clamp(24px,3vw,36px);line-height:1.2;margin:16px 0}.iq-report p,.iq-report small{color:#c1c3cb}
      .report-overview{display:flex;gap:32px;align-items:center;padding:24px 0;border-bottom:1px solid #41434a}.report-ring{position:relative;width:160px;min-width:160px;height:160px}.report-ring svg{width:100%;height:100%;transform:rotate(-90deg)}circle{fill:none;stroke-width:7}.ring-track{stroke:#393b43}.ring-value{stroke:#35d8c7;stroke-linecap:round;animation:ring-in 1s ease-out}.report-ring>div{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;align-items:center}.report-ring strong{font-size:42px;line-height:1.2}.report-ring span{font-size:12px;color:#b9bbc5}
      .assessment-list{display:flex;gap:12px;flex-wrap:wrap;font-size:13px}.topic-performance{margin:20px 0}.topic-performance>div{display:flex;justify-content:space-between;gap:20px}.topic-performance progress{width:100%;height:8px;accent-color:#35d8c7}.report-findings{display:grid;grid-template-columns:1fr 1fr;gap:24px}.report-findings section:last-child{grid-column:1/-1}.report-findings ul{padding-left:20px}.report-findings li{margin:12px 0}.report-evidence{border-top:1px solid #41434a;padding:20px 0}.report-evidence summary{cursor:pointer;font-weight:600}.report-actions{display:flex;flex-wrap:wrap;gap:12px}.report-actions a,.report-actions button{background:#ff785f;color:#171536;padding:12px 18px;border:0;border-radius:10px;text-decoration:none;font:inherit;cursor:pointer}.report-actions button{background:#393b43;color:#fff}.iq-report :focus-visible{outline:3px solid #35d8c7;outline-offset:4px}.report-confetti{position:absolute;right:24px;top:12px;pointer-events:none}.report-confetti i{display:inline-block;color:#ff785f;margin:0 6px;animation:confetti 1.5s ease-out both}.report-confetti i:nth-child(even){color:#35d8c7;animation-delay:.15s}
      @keyframes ring-in{from{stroke-dasharray:0 100}}@keyframes confetti{from{transform:translateY(-30px) rotate(0);opacity:0}to{transform:translateY(12px) rotate(140deg);opacity:1}}
      @media(max-width:600px){.report-overview{flex-direction:column;align-items:flex-start}.report-findings{grid-template-columns:1fr}.report-confetti{position:static}}@media(prefers-reduced-motion:reduce){.ring-value,.report-confetti i{animation:none}}@media print{.report-actions,.report-confetti{display:none}.iq-report{background:white;color:black}.iq-report p{color:#333}}
    `}</style>
  </section>;
}
