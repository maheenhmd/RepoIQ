# Phase 4A: adaptive text interviews

Core flow previously verified by the owner; latest MVP changes are NOT RUN.
See [backend MVP audit and runbook](backend-mvp.md) for current reporting and policies.
Each answer drives one decision: follow up,
explore another code-backed topic, or finish. No question bank is generated.

## Contracts and flow

- `POST /api/interviews/start`: `request_id` (UUID, recommended), `repository_id`,
  `topic` (1–120 characters), `difficulty` (`beginner`, `intermediate`, `advanced`),
  `max_turns` (default 8; server default maximum 12, hard maximum 20).
- `POST /api/interviews/{session_id}/answers`: `request_id` (new UUID per answer),
  `expected_version` from the last response, `answer` (1–6000 characters).
- `GET /api/interviews/{session_id}`: current state and ordered conversation.
- `GET /api/interviews/{session_id}/report`: final persisted practice report (409 while active).

The service reuses repository/model-scoped hybrid retrieval, keeps one commit
snapshot, and sends bounded excerpts plus recent history through `LLMProvider`.
`OllamaProvider` uses the [official structured chat API](https://docs.ollama.com/api/chat)
with JSON schema, nonstreaming output and generation limits. Repository text,
candidate answers and history are untrusted data, never tool instructions.
The provider cannot execute code or call tools. The API never downloads models.

The LLM returns a decision, question, qualitative feedback, topic/difficulty and
citation IDs. The service checks decision consistency, turn limits, repeated
questions and citation membership. Paths, commit SHAs, symbols, line ranges and
excerpts come exclusively from retrieved data. Feedback is practice feedback,
not a hiring judgment; valid citations cannot prove the model's reasoning.

`interview_sessions` and `interview_turns` persist settings, version, status,
answers, responses and bounded evidence snapshots. The first question is version
0; every accepted answer increments version and answered_turns together. A turn's
answer responds to the preceding question; its response contains feedback and the
next question. Progress is a maximum, not a predetermined question count.

Inference holds no database connection or transaction. A short transaction compares
the expected version, advances state and inserts the turn atomically. Conflicting
answers receive 409. Identical request IDs/bodies replay committed responses after
retries or restarts; changed input with a reused ID fails. Start request IDs also
serve as session IDs. Keep IDs for retries; omission generates a fresh ID. Failed
generation never advances state. Multiple API processes may duplicate inference
work, but cannot commit conflicting turns. Existing migrations remain unchanged.

## Configuration and limits

See `backend/.env.example`. `OLLAMA_ENDPOINT` only accepts a loopback HTTP(S)
origin; proxies and redirects are disabled. Default `OLLAMA_MODEL=qwen2.5-coder:1.5b` is a
configurable local starter choice, not a quality benchmark. Ollama supports CPU;
latency/memory depend on the machine and model.

Defaults: 180-second HTTP timeout, 512 output tokens, 4096 context tokens, 4
retrieval results, 4000 source characters, 1000 characters per excerpt and 6000
history characters. One generation per API process; concurrent calls receive 429.
A UTF-8-size token estimate (two bytes per token) reserves output/template space and discards
old history, lower-priority sources, then whole lines. Candidate answers are never
silently truncated; impossible budgets return 409. Long single-line chunks may be
skipped. Use a model with a sufficient native context window; this estimate does
not replace a model-specific tokenizer. Model responses are capped at 64 KiB.

Original question evidence is retained ahead of fresh retrieval; other commits are
filtered out. Missing/truncated evidence limits evaluation and topic exploration.
Unavailable Ollama/missing model returns 503; timeouts 504; malformed output or
invalid citations 502. No cloud fallback or state advance on errors. Logs contain
exception types only, never prompts, answers, source code or credentials.

No authentication or retention/deletion API yet: use locally on loopback. Answers
and bounded evidence are stored in Neon. No new dependencies, ingestion changes,
model downloads, frontend, advanced scoring dashboard or voice implementation.

## Manual PowerShell verification — NOT RUN

With Ollama installed, start it if its desktop app is not already serving:

```powershell
ollama serve
```

In another window (manual model provisioning and unapplied migration):

```powershell
# Use the already installed qwen2.5-coder:1.5b; model provisioning is separate.
Set-Location 'C:\Users\HP\Desktop\RepoIQ\backend'
# Existing DATABASE_URL / DIRECT_DATABASE_URL configuration is required.
uv run alembic upgrade head
uv run alembic current
uv run pytest tests/test_interviews.py -q
$env:OLLAMA_MODEL = 'qwen2.5-coder:1.5b'
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another window, use an already indexed repository ID:

```powershell
$base = 'http://127.0.0.1:8000/api/interviews'
$startBody = @{
  request_id = [guid]::NewGuid().ToString()
  repository_id = (Read-Host 'Indexed repository UUID')
  topic = 'error handling'
  difficulty = 'intermediate'
  max_turns = 3
} | ConvertTo-Json
$turn = Invoke-RestMethod -Method Post -Uri "$base/start" -ContentType 'application/json' -Body $startBody
$turn | ConvertTo-Json -Depth 10

# Repeat this block for each answer while $turn.status is 'active'.
$answerBody = @{
  request_id = [guid]::NewGuid().ToString()
  expected_version = $turn.version
  answer = (Read-Host 'Your answer')
} | ConvertTo-Json
$answerUrl = "$base/$($turn.session_id)/answers"
$turn = Invoke-RestMethod -Method Post -Uri $answerUrl -ContentType 'application/json' -Body $answerBody
$turn | ConvertTo-Json -Depth 10

# Identical retry must not increment the version.
$replay = Invoke-RestMethod -Method Post -Uri $answerUrl -ContentType 'application/json' -Body $answerBody
$replay.version -eq $turn.version

# Repeat after restarting the API; state/history must survive.
Invoke-RestMethod -Uri "$base/$($turn.session_id)" | ConvertTo-Json -Depth 12
```

Mocked tests cover adaptive actions, citations, context limits, retries, stale
versions, safe errors and transaction boundaries. They use no real DB or models.
Real PostgreSQL concurrency and local model quality need manual verification.

## Changed files

- `backend/app/api/interviews.py`: start, answer, history routes.
- `backend/app/schemas/interview.py`: requests, decisions, feedback, citations.
- `backend/app/services/question_generator.py`: adaptive flow and RAG context.
- `backend/app/integrations/llm_client.py`: provider interface and Ollama adapter.
- `backend/app/core/config.py`, `backend/.env.example`: limits and local settings.
- `backend/app/db/models.py`, `backend/app/db/interviews.py`: state and atomic writes.
- `backend/migrations/versions/20261029_0006_interviews.py`: additive tables.
- `backend/tests/test_interviews.py`: mocked coverage, NOT RUN.
- `docs/interviews.md`, `docs/architecture.md`, `docs/milestones.md`: contracts/status.

Asaan alfaaz mein: har jawab ke baad AI relevant code dekh kar agla sawal tay karta
hai. Database guftagu aur version sambhalta hai, is liye restart ya retry se jawab
do baar save nahi hota. Agla milestone: owner ki local end-to-end tasdeeq.
