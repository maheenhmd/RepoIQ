"""Versioned, reproducible practice report. No inference or database writes."""
from collections import Counter

from app.integrations.llm_client import LLMError
from app.schemas.interview import ConversationTurn, InterviewReport, ReportEvaluation, TopicPerformance

CORRECTNESS = {'correct': 100, 'partial': 50, 'incorrect': 0, 'uncertain': 0}
DEPTH = {'surface': 25, 'reasoned': 65, 'detailed': 100}
EXPLANATION = (
    'AI-generated practice feedback, not a hiring assessment. practice-v1: overall score '
    'is the arithmetic mean of recorded correctness ratings (correct=100, partial=50, '
    'incorrect=0, uncertain=0). Uncertain means no demonstrated correctness, not proven '
    'lack of knowledge. Depth is separate: surface=25, reasoned=65, detailed=100; '
    'unassessed is excluded and reported as null when no depth ratings exist. '
    'Each answered turn has equal weight; topic scores use the topic of the question answered.'
)


def mean(values):
    return round(sum(values) / len(values), 1) if values else None


def build_report(raw_turns: list[dict]) -> InterviewReport:
    turns = [ConversationTurn.model_validate(turn) for turn in raw_turns]
    if not turns or turns[-1].response.status != 'finished':
        raise LLMError('Final report is available after interview completion', 409)
    final = turns[-1].response
    if turns[0].response.version != 0 or any(
        t.response.session_id != final.session_id or t.response.repository_id != final.repository_id
        or t.response.commit_sha != final.commit_sha
        or any(r.commit_sha != final.commit_sha for r in t.response.sources)
        for t in turns
    ):
        raise LLMError('Interview history identity is inconsistent', 409)
    evaluations = []
    for previous, turn in zip(turns, turns[1:]):
        before, after = previous.response, turn.response
        if (after.session_id != final.session_id or after.repository_id != final.repository_id
                or after.commit_sha != final.commit_sha or after.version != before.version + 1
                or turn.answer is None or before.question is None or after.feedback is None):
            raise LLMError('Interview history is incomplete; report cannot be calculated', 409)
        # Attribute evaluation to the question answered, not the newly chosen topic.
        refs = { (r.chunk_id, r.start_line, r.end_line): r for r in before.sources }
        evaluations.append(ReportEvaluation(
            turn=after.version, topic=before.topic, difficulty=before.difficulty,
            question=before.question, answer=turn.answer, feedback=after.feedback,
            correctness_score=CORRECTNESS[after.feedback.assessment],
            depth_score=DEPTH.get(after.feedback.depth), sources=list(refs.values()),
        ))
    if len(evaluations) != final.answered_turns:
        raise LLMError('Interview progress does not match recorded answers', 409)
    groups = {}
    strengths, weaknesses, gaps, recommendations = [], [], [], []
    for item in evaluations:
        groups.setdefault(item.topic.casefold(), []).append(item)
        finding = f'Question {item.turn} ({item.topic}): {item.feedback.rationale}'
        if item.feedback.assessment == 'correct':
            strengths.append(finding)
        else:
            weaknesses.append(finding)
            gaps.extend(f'Question {item.turn}: {concept}' for concept in item.feedback.missed_concepts)
            if not item.feedback.missed_concepts:
                gaps.append(f'Not yet demonstrated in question {item.turn}: {item.question}')
            locations = ', '.join(f'{r.file_path}:{r.start_line}-{r.end_line}' for r in item.sources)
            recommendations.append(f'Read {locations or "the recorded question evidence"}; trace the control flow '
                                   f'and retry question {item.turn}: {item.question}')
    topics = [TopicPerformance(topic=items[0].topic, answers=len(items),
        correctness_score=mean([x.correctness_score for x in items]),
        depth_score=mean([x.depth_score for x in items if x.depth_score is not None]),
        depth_assessed_answers=sum(x.depth_score is not None for x in items)) for items in groups.values()]
    score = mean([x.correctness_score for x in evaluations])
    counts = Counter(x.feedback.assessment for x in evaluations)
    return InterviewReport(
        session_id=final.session_id, repository_id=final.repository_id, commit_sha=final.commit_sha,
        overall_score=score, technical_correctness=score,
        depth_score=mean([x.depth_score for x in evaluations if x.depth_score is not None]),
        depth_assessed_answers=sum(x.depth_score is not None for x in evaluations),
        answered_turns=len(evaluations), assessment_counts={key: counts[key] for key in CORRECTNESS},
        topics=topics, strengths=strengths, weaknesses=weaknesses, knowledge_gaps=gaps,
        recommendations=recommendations, evaluations=evaluations,
        summary=f'Completed {len(evaluations)} answered turns across {len(topics)} topics. '
                + ('Configured turn limit reached.' if final.answered_turns >= final.max_turns else 'Completed early.'),
        score_explanation=EXPLANATION,
    )
