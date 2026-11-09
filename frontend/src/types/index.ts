export type Difficulty = 'beginner' | 'intermediate' | 'advanced';
export type Source = { source_id: string; chunk_id: string; file_path: string; commit_sha: string; symbol_name: string; start_line: number; end_line: number; content: string };
export type Feedback = { evaluated?: boolean; assessment: 'correct' | 'partial' | 'incorrect' | 'uncertain'; rationale: string; depth: string; missed_concepts: string[] };
export type Report = { overall_score: number | null; summary: string; score_explanation: string; assessment_counts: Record<string, number>; topics: { topic: string; correctness_score: number; depth_score: number | null }[]; strengths: string[]; weaknesses: string[]; recommendations: string[]; evaluations: { turn: number; sources: Source[] }[] };
export type Interview = { session_id: string; repository_id: string; commit_sha: string; version: number; status: 'active' | 'finished'; action: string; topic: string; difficulty: Difficulty; question: string | null; feedback: Feedback | null; sources: Source[]; topics: string[]; answered_turns: number; max_turns: number; report: Report | null };
export type Turn = { request_id: string; answer: string | null; response: Interview };
export type History = { current: Interview; turns: Turn[] };
