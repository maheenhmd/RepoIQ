"""Deterministic interview policy around evidence-based model evaluations."""
import re

LEVELS = ('beginner', 'intermediate', 'advanced')


def is_explicit_non_answer(answer: str | None) -> bool:
    normalized = ' '.join(re.sub(r'[^\w\s]', ' ', (answer or '').casefold()).split())
    return normalized in {'', 'i do not know', 'i don t know', 'i dont know',
                          'no idea', 'i have no idea', 'not sure', 'i am not sure',
                          'idk', 'mujhe nahi pata', 'pata nahi'}


def question_key(question: str) -> str:
    return ' '.join(re.findall(r'\w+', question.casefold()))


def correct_streak(turns: list[dict]) -> int:
    count = 0
    for turn in reversed(turns):
        feedback = turn['response'].get('feedback')
        if not feedback or feedback['assessment'] != 'correct':
            break
        count += 1
    return count


def apply_policy(draft, state):
    """Never relabel an off-topic question as grounded; fail before persisting it."""
    if draft.feedback is None:
        raise ValueError('Missing evaluation')
    if is_explicit_non_answer(state['answer']):
        feedback = draft.feedback.model_copy(update={
            'assessment': 'uncertain', 'depth': 'unassessed', 'missed_concepts': [],
            'rationale': 'The candidate explicitly stated they could not answer the question.',
        })
        draft = draft.model_copy(update={'feedback': feedback})
    assessment = draft.feedback.assessment
    if assessment == 'correct' and draft.feedback.missed_concepts:
        raise ValueError('Correct evaluation contradicts recorded missing concepts')
    if assessment == 'uncertain':
        draft = draft.model_copy(update={'feedback': draft.feedback.model_copy(update={'depth': 'unassessed'})})
    updates = {'difficulty': state['difficulty']}
    if state['must_finish']:
        # Completion is a server limit, not an LLM preference. Feedback/citations
        # are still validated; an unneeded next question is simply not retained.
        updates.update(action='finish', question=None, topic=state['topic'])
    else:
        same_topic = question_key(draft.topic) == question_key(state['topic'])
        if assessment != 'correct' and (not same_topic or draft.action == 'finish'):
            raise ValueError('Incomplete understanding requires an on-topic follow-up')
        if same_topic and draft.action in {'follow_up', 'change_topic'}:
            updates.update(action='follow_up', topic=state['topic'])
    return draft.model_copy(update=updates)
