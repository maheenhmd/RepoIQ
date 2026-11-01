import type { Feedback } from '@/types';
export default function FeedbackPanel({ feedback }: { feedback: Feedback }) {
  return <section className={`feedback ${feedback.assessment}`} aria-label="Answer feedback">
    <strong>{feedback.assessment}</strong><p>{feedback.rationale}</p>
    {!!feedback.missed_concepts?.length && <p>Explore next: {feedback.missed_concepts.join(' · ')}</p>}
  </section>;
}
