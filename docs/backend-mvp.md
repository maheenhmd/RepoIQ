# Backend MVP — implementation audit and owner runbook

2026-10-31. **This change was inspected and edited only. Tests, scripts, servers,
database queries, migrations, API requests, inference and downloads were NOT RUN.**
The owner previously reported successful start/answer/history behavior and 32
interview tests. That report is not verification of these new changes.

## Audit and changes

| Area | Existing implementation preserved | This change / practical boundary |
|---|---|---|
| Import | GitHub URL validation, metadata, discovery/filtering and previews | No rebuild; previews remain nonpersistent |
| Durable ingestion | PostgreSQL queue, pinned commit/blob checks, size/batch limits, retries, cancellation, file/chunk upserts | Dedicated ingestion worker still required |
| Indexing | AST/Tree-sitter/text chunks, CodeRankEmbed 768D, resumable embedding CLI, model provenance | Embedding worker remains separate; ingestion success does not mean embeddings are ready |
| Search | Repository/model SQL isolation, vector/FTS/symbol/filename retrieval, RRF, optional ONNX reranking, filters | Unchanged; obsolete code_indexer/code_retriever placeholders are not the active path |
| Interview | Local Ollama adapter, bounded implementation context, canonical citations, structured output validation | Python policies now own completion, action normalization, nominal difficulty and duplicate keys |
| Evaluation | Correct/partial/incorrect/uncertain with rationale | Optional depth and missed concepts; irrelevant answers map to incorrect, preserving the existing enum |
| Sessions | Persisted history, version checks, request-ID replay, atomic writes without holding DB locks during inference | Preserved; report snapshot shares final-turn commit |
| Reports | Missing | Deterministic rubric, topic metrics, strengths/gaps/recommendations and source evidence |
| API reliability | Safe failures and health/OpenAPI | Additive report/readiness endpoints and Retry-After on retryable interview responses |
| Tests/docs | Mocked interview/search suites | Updated policy tests and new report/readiness coverage, not executed |

## Interview rules and reporting

The model still evaluates technical meaning against retrieved evidence. Python
cannot prove arbitrary answers correct. It enforces these explicit rules:

- A clear non-answer such as "I do not know" becomes uncertain, with depth unassessed.
  Substantive answers containing uncertainty are not automatically overwritten.
- Partial, incorrect and uncertain evaluations require an on-topic follow-up until
  the configured turn limit. A proposed off-topic question is rejected, not relabeled.
- A question on the same topic is a follow-up even if the model labels it a topic change.
- A correct evaluation permits a topic transition or early finish. Two consecutive
  correct answers raise nominal difficulty one step. Incorrect or explicit non-answer lowers it
  one step; partial keeps it. Levels are clamped to beginner/intermediate/advanced.
  The prompt receives the same policy; complexity matching still needs human review.
  Substantive answers judged uncertain retain difficulty: missing reference evidence
  does not demonstrate poor performance. Evaluation compares meaning, not identical
  wording, and requires rationale identifying support, omissions, contradictions or
  unavailable evidence. Answer-time capacity overflow rejects rather than silently
  shortening the last reference. Semantic accuracy still requires owner inference checks.
- On the final allowed answer, Python sets finished and removes an unnecessary next
  question, while still requiring valid evaluation and canonical citation IDs.
- Duplicate comparison ignores case, punctuation and Markdown quoting. Semantic
  paraphrase detection is not guaranteed and does not use a new model.
- Structurally invalid, truncated, unknown-citation or off-topic output is not committed.
  Errors remain safe; retry using the same request ID and expected version.

`Feedback.depth` is optional: unassessed, surface, reasoned or detailed.
`Feedback.missed_concepts` is optional, at most three short strings describing gaps
supported by the question/code. Old feedback remains valid; missing values are not
fabricated. The model is instructed to distinguish the candidate's words from source
knowledge and to preserve precise technical conditions in its question wording.

**practice-v1 scoring:** overall and technical_correctness are the arithmetic mean
over answered turns: correct=100, partial=50, incorrect=0, uncertain=0, rounded to one
decimal. Uncertain earns no demonstrated-correctness credit; this is not proof the
candidate lacks knowledge. Difficulty does not change the weight. Topic attribution
uses the question answered, never the next topic selected by the model.

Depth is reported separately: surface=25, reasoned=65, detailed=100. Unassessed turns
are excluded; no depth evidence means `depth_score: null`. Coverage is returned.
Depth never silently affects overall score. Scores are practice estimates derived
from recorded AI assessments, not objective hiring judgments.

Reports include every scored answer/question, original difficulty, recorded feedback,
supporting references, topic metrics, assessment counts, strengths/weaknesses,
recorded missed concepts and actionable code-review recommendations. No extra model
call generates the report. Missing concepts in old records are described as an
unanswered question, not invented named technical gaps.

New reports are stored as `response.report` in the existing final `interview_turns`
JSONB row. State, answer, evaluation and report commit atomically. Report GET reuses
that snapshot after restart. Legacy finished sessions are calculated from their
saved transcript with practice-v1, without writes or migrations. Incomplete or
inconsistent histories return 409 rather than fabricated scores. Preserve this
rubric version if adding a different formula later.

## API contracts

All paths below are preserved except the two explicitly marked new routes.

| Method/path | Meaning |
|---|---|
| GET /health | Dependency-free liveness: `{"status":"ok"}` |
| GET /ready **new** | 200/503 with database and installed-Ollama-model flags; no inference |
| GET /docs, /openapi.json | FastAPI generated contracts |
| POST /api/repositories/preview | GitHub metadata preview |
| POST /api/repositories/files | File discovery |
| POST /api/repositories/files/filtered | Eligible files |
| POST /api/repositories/file-content | Single source file |
| POST /api/repositories/ingest/preview | Bounded nonpersistent preview |
| POST /api/repositories/ingest | Queue durable ingestion, 202 |
| GET /api/repositories/ingest/{job_id} | Progress and repository ID |
| GET /api/repositories/ingest/{job_id}/errors | Paginated errors |
| POST /api/repositories/ingest/{job_id}/cancel | Cancel between batches |
| POST /api/repositories/{repository_id}/search | Hybrid search |
| POST /api/interviews/start | First question; UUID request_id, repository_id, topic, difficulty, max_turns |
| POST /api/interviews/{session_id}/answers | UUID request_id, expected_version, answer |
| GET /api/interviews/{session_id} | Current response and saved turns; use to resume |
| GET /api/interviews/{session_id}/report **new** | Final practice report; active session=409, missing=404 |

Responses add optional `report` (null while active) and optional feedback fields.
Existing fields, UUIDs and version semantics stay intact. Start version=0; every
accepted answer increments version/answered_turns once. Use a new request ID for a
new answer and reuse the identical ID/body on retry. Stale versions or changed
payloads under a used ID receive 409. Per-process busy responses are 429; multiple
processes can infer concurrently but the database version guard permits only one
commit. Failures do not advance progress. Retry-After is set for 429/503/504.

`/ready` checks required DB tables and whether Ollama advertises the configured
model. It does not prove inference speed, repository embedding completeness, worker
availability, or quality. It has short time/size limits and never returns secrets.
The health endpoint stays usable if DB/Ollama is unavailable.

## Manual PowerShell commands (owner only, not executed)

Prerequisites: existing backend environment, migration 0006 already applied,
existing Neon configuration and installed qwen2.5-coder:1.5b/CodeRankEmbed artifacts.
**No migration, install or model download is needed for this change.**

Window A — tests, then API:

```powershell
Set-Location 'C:\Users\HP\Desktop\RepoIQ\backend'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
uv run --no-sync python -m pytest -q
uv run --no-sync python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
```

Start the installed Ollama app separately if it is not running; do not download a
model as part of verification. Process environment overrides backend `.env`; restart
the API after changing settings because factories cache them. Defaults now match
the selected CPU setup: model qwen2.5-coder:1.5b, timeout 180, output 512 tokens,
context 4096 tokens, four excerpts, total 4000 characters, each at most 1000.

Window B — check dependencies:

```powershell
$api = 'http://127.0.0.1:8000'
Invoke-RestMethod "$api/health"
Invoke-RestMethod "$api/ready"
```

Optional fresh import (skip this section for an already indexed repository):

```powershell
$jobBody = @{url='https://github.com/psf/requests'; request_id=[guid]::NewGuid().ToString()} | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -Uri "$api/api/repositories/ingest" -ContentType 'application/json' -Body $jobBody
$job.id
```

Window C — run the existing ingestion worker; keep it running while polling:

```powershell
Set-Location 'C:\Users\HP\Desktop\RepoIQ\backend'
uv run --no-sync python -m app.workers.ingestion
```

Window B — poll until succeeded (failed/cancelled requires inspection, not guessing):

```powershell
$job = Invoke-RestMethod "$api/api/repositories/ingest/$($job.id)"
$job | ConvertTo-Json -Depth 6
# If failed:
# Invoke-RestMethod "$api/api/repositories/ingest/$($job.id)/errors"
```

After ingestion succeeds, Window D — drain pending embeddings using existing artifacts:

```powershell
Set-Location 'C:\Users\HP\Desktop\RepoIQ\backend'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
uv run --no-sync python -m app.workers.embeddings --batch-size 4
```

Window B — search and interview (use `$job.repository_id` or an existing UUID):

```powershell
$repoId = Read-Host 'Indexed repository UUID'
$searchBody = @{query='How are HTTP errors handled?'; top_k=5} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$api/api/repositories/$repoId/search" -ContentType 'application/json' -Body $searchBody
$startBody = @{
  request_id=[guid]::NewGuid().ToString(); repository_id=$repoId
  topic='HTTP authentication and error handling'; difficulty='intermediate'; max_turns=3
} | ConvertTo-Json
$turn = Invoke-RestMethod -Method Post -Uri "$api/api/interviews/start" -ContentType 'application/json' -Body $startBody -TimeoutSec 240
$sessionId = $turn.session_id
$turn | ConvertTo-Json -Depth 12
# Before completion, GET /report should return 409.
while ($turn.status -eq 'active') {
  $answerBody = @{
    request_id=[guid]::NewGuid().ToString(); expected_version=$turn.version
    answer=(Read-Host 'Your answer (try I do not know on one turn)')
  } | ConvertTo-Json
  $turn = Invoke-RestMethod -Method Post -Uri "$api/api/interviews/$sessionId/answers" -ContentType 'application/json' -Body $answerBody -TimeoutSec 240
  $turn | ConvertTo-Json -Depth 15
}
$report = Invoke-RestMethod "$api/api/interviews/$sessionId/report"
$report | ConvertTo-Json -Depth 15
$history = Invoke-RestMethod "$api/api/interviews/$sessionId"
$history.turns.Count
# Retry the last exact body: no additional turn or model generation.
$replay = Invoke-RestMethod -Method Post -Uri "$api/api/interviews/$sessionId/answers" -ContentType 'application/json' -Body $answerBody
$replay.version -eq $turn.version
```

On a 502/503/504, retain `$answerBody`; do not generate another ID before retrying.
After restarting the API in Window A, repeat report/history GETs. The persisted
report should match, including rubric version and source references. To check
conflicts, submit different IDs with the same expected_version from two windows:
only one may commit; the other receives busy/stale-state handling (429/409).

Expected: source-backed questions, uncertain for a clear non-answer, focused
follow-ups, bounded completion with question=null, rubric_version=practice-v1,
score within 0–100, correct topic attribution, null depth for legacy unassessed
feedback, repeatable history/report and unchanged version on identical retries.
The test command should have no failures; no passing result is claimed here.

## Files changed and limitations

- `app/services/answer_evaluator.py`: pure deterministic policy, non-answer handling, duplicate key.
- `app/services/question_generator.py`: policy/prompt integration, final report snapshot, report lookup.
- `app/services/interview_report.py`: deterministic, versioned report derived from persisted turns.
- `app/schemas/interview.py`: optional evaluation fields and typed report contracts.
- `app/api/interviews.py`: report route and retry headers.
- `app/api/health.py`, `app/db/health.py`, `app/main.py`: bounded readiness endpoint.
- `app/core/config.py`, `.env.example`: stable configuration path and selected CPU defaults.
- `tests/test_interviews.py`, `tests/test_interview_mvp.py`: new/updated mocked coverage only.
- `README.md`, `docs/interviews.md`, `docs/architecture.md`, `docs/milestones.md`, this guide: current contracts/status.

No dependencies, model changes, migrations, frontend, voice, auth or deployment.
Use loopback for this local MVP. Authentication/ownership, retention/deletion,
production rate limiting, CORS policy and deployment hardening remain separate work.
Render all repository/model text as untrusted text in the future frontend. Lexical
grounding/duplicate checks cannot prove semantics; small local models can still
misjudge answers or wording, and invalid output remains a retryable user-visible
failure rather than fabricated success. Context packing uses a token estimate, not
a model tokenizer; oversized context is rejected. Readiness is not a load test.
Embedding indexing remains a separate explicit worker step and does not automatically
regenerate vectors from an incompatible model. No tests or runtime checks were run.

Asaan alfaaz mein: AI jawab ko code se compare karta hai; Python interview ke rules
aur saved evaluations se score nikalta hai. Final report usi transaction mein save
hoti hai, is liye restart ke baad bhi wahi report milti hai.
