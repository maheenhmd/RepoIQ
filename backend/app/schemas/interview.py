"""Validated chat contracts; source metadata is always supplied by the server."""
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

Difficulty = Literal['beginner', 'intermediate', 'advanced']
Action = Literal['ask', 'follow_up', 'change_topic', 'finish']


class StartInterview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID = Field(default_factory=uuid4)
    repository_id: UUID
    topic: str = Field(min_length=1, max_length=120, strict=True)
    difficulty: Difficulty = 'intermediate'
    max_turns: int = Field(default=8, ge=1, le=20, strict=True)

    @field_validator('topic')
    @classmethod
    def clean_topic(cls, value):
        if not value.strip() or '\0' in value:
            raise ValueError('Provide a nonempty topic')
        return value.strip()


class CandidateAnswer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID = Field(default_factory=uuid4)
    expected_version: int = Field(ge=0, le=20, strict=True)
    answer: str = Field(min_length=1, max_length=6000, strict=True)

    @field_validator('answer')
    @classmethod
    def clean_answer(cls, value):
        if not value.strip() or '\0' in value:
            raise ValueError('Provide a nonempty answer')
        return value.strip()


class Feedback(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    assessment: Literal['correct', 'partial', 'incorrect', 'uncertain']
    rationale: str = Field(min_length=10, max_length=1500)
    # Optional for old saved turns and existing clients. Never infer depth from length.
    depth: Literal['unassessed', 'surface', 'reasoned', 'detailed'] = 'unassessed'
    missed_concepts: list[Annotated[str, Field(min_length=1, max_length=160)]] = Field(default_factory=list, max_length=3)

    @field_validator('missed_concepts')
    @classmethod
    def clean_concepts(cls, values):
        if any(not value.strip() or '\0' in value for value in values):
            raise ValueError('Invalid missed concept')
        return list(dict.fromkeys(value.strip() for value in values))


class InterviewDraft(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    action: Action
    topic: str = Field(min_length=1, max_length=120)
    difficulty: Difficulty
    question: str | None = Field(min_length=10, max_length=1500)
    feedback: Feedback | None
    source_ids: list[str] = Field(min_length=1, max_length=3)


class QuestionSource(BaseModel):
    source_id: str
    chunk_id: str
    file_path: str
    commit_sha: str
    symbol_name: str
    start_line: int
    end_line: int
    content: str


class ReportEvaluation(BaseModel):
    turn: int
    topic: str
    difficulty: Difficulty
    question: str
    answer: str
    feedback: Feedback
    correctness_score: float = Field(ge=0, le=100)
    depth_score: float | None = Field(default=None, ge=0, le=100)
    sources: list[QuestionSource]


class TopicPerformance(BaseModel):
    topic: str
    answers: int
    correctness_score: float = Field(ge=0, le=100)
    depth_score: float | None = Field(default=None, ge=0, le=100)
    depth_assessed_answers: int


class InterviewReport(BaseModel):
    session_id: UUID
    repository_id: UUID
    commit_sha: str
    rubric_version: Literal['practice-v1'] = 'practice-v1'
    overall_score: float | None = Field(default=None, ge=0, le=100)
    technical_correctness: float | None = Field(default=None, ge=0, le=100)
    depth_score: float | None = Field(default=None, ge=0, le=100)
    depth_assessed_answers: int
    answered_turns: int
    assessment_counts: dict[str, int]
    topics: list[TopicPerformance]
    strengths: list[str]
    weaknesses: list[str]
    knowledge_gaps: list[str]
    recommendations: list[str]
    evaluations: list[ReportEvaluation]
    summary: str
    score_explanation: str


class InterviewResponse(BaseModel):
    session_id: UUID
    repository_id: UUID
    commit_sha: str
    version: int
    status: Literal['active', 'finished']
    action: Action
    topic: str
    difficulty: Difficulty
    question: str | None
    feedback: Feedback | None
    sources: list[QuestionSource]
    topics: list[str]
    answered_turns: int
    max_turns: int
    report: InterviewReport | None = None


class ConversationTurn(BaseModel):
    request_id: UUID
    answer: str | None
    response: InterviewResponse


class InterviewHistory(BaseModel):
    current: InterviewResponse
    turns: list[ConversationTurn]
