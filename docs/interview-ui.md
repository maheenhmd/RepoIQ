# Interview workspace (implementation only)

Frontend root: `C:\Users\HP\Desktop\RepoIQ\frontend`. Route: `/interview`.
No tests, builds, servers, API calls, installs or inference were executed.
The reference image was not present in the attachment; styling follows the supplied
navy/coral/teal palette. No new packages or backend changes.

## Changed files

- `frontend/src/app/interview/page.tsx`: setup, conversation, composer, UUID/version
  submission, per-tab recovery, pending-request replay and error states.
- `frontend/src/app/interview/workspace.css`: responsive, scoped visual styling.
- `frontend/src/components/QuestionCard.tsx`: question and expandable canonical citations.
- `frontend/src/components/FeedbackPanel.tsx`: actual assessment and rationale.
- `frontend/src/components/InterviewReport.tsx`: actual scores, topics and recommendations.
- `frontend/src/types/index.ts`: backend response contracts used by the workspace.
- `frontend/src/lib/api.ts`: bounded requests and safe errors; existing export preserved.
- `frontend/src/app/api/backend/[...path]/route.ts`: fixed-upstream, allowlisted proxy.
- This guide, `docs/architecture.md`, `docs/milestones.md`: implementation status.

Browser requests go to Next.js `/api/backend/...`, which forwards only interview
and readiness routes to FastAPI. Server-only `BACKEND_URL` defaults to
`http://127.0.0.1:8000`. CORS changes are unnecessary. No secrets reach the browser.
Existing `NEXT_PUBLIC_API_BASE_URL` is not used by this workspace proxy.

Candidate/model text is rendered as text, never HTML. Pending request bodies and
drafts live in sessionStorage for this tab; avoid shared browsers. History/report
remain in PostgreSQL. New Interview clears only the tab pointer, not backend data.
Keep the displayed session UUID for later retrieval. There is no session list or auth.
Explicit retries reuse UUID/body; 409 reloads current history; 422 enables input
correction. API errors preserve answers. CPU generation may take several minutes.

## Owner verification

Use existing installed dependencies and the existing running Ollama application.
PowerShell window 1:

```powershell
Set-Location 'C:\Users\HP\Desktop\RepoIQ\backend'
uv run --no-sync python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

PowerShell window 2:

```powershell
Set-Location 'C:\Users\HP\Desktop\RepoIQ\frontend'
$env:BACKEND_URL = 'http://127.0.0.1:8000'
npm run dev
```

Open http://localhost:3000/interview. If dependencies are missing, startup requires
owner installation first; none were installed for this change.

1. Confirm readiness; start with the provided local repository UUID and three turns.
2. Confirm code-backed question, citations, difficulty, and version progression.
3. Submit answers with Enter; verify Shift+Enter and IME composition do not submit.
4. Refresh while idle and while generation is pending; verify history restoration
   and that retrying the same request never adds duplicate turns.
5. Disconnect the backend: answer must remain visible with a useful retry message.
6. Complete and inspect actual score, topic breakdown, recommendations and evidence.
7. Refresh again; report/history must persist. Check mobile width and keyboard focus.
8. Verify 422 correction and concurrent-tab 409 recovery manually.

No runtime success is claimed. Local proxy is not a public deployment security
boundary. Visual matching to the missing image and CPU timeout behavior need review.

Asaan alfaaz mein: browser Next.js ko request deta hai, Next.js FastAPI tak pohanchata
hai. Wahi request ID dobara bhejne se aik jawab do martaba save nahi hota.
