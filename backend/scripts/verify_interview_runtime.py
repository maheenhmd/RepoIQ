"""Real local HTTP/Ollama/Neon smoke check. Creates development interview sessions."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal
from app.db.models import Repository, CodeChunk

def main():
    with SessionLocal() as db:
        repo = db.scalar(select(Repository.id).where(Repository.owner == "psf", Repository.name == "requests"))
    if repo is None:
        raise RuntimeError("Indexed psf/requests repository not found")
    env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1", "--port", "8017", "--log-level", "warning"], env=env)
    base = "http://127.0.0.1:8017"
    try:
        with httpx.Client(timeout=300, trust_env=False) as client:
            for _ in range(60):
                try:
                    if client.get(base + "/health", timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("Verification server failed to start")
            for attempt in range(2):
                r = client.post(base + "/api/interviews/start", json=dict(request_id=str(uuid4()),
                    repository_id=str(repo), topic="HTTP authentication and error handling",
                    difficulty="intermediate", max_turns=3))
                print("START", attempt + 1, r.status_code, flush=True)
                if r.status_code != 200:
                    print(r.json(), flush=True)
                    raise RuntimeError("Start failed")
                turn = r.json()
                print("QUESTION", turn["question"], flush=True)
                print("SOURCES", [(s["file_path"], s["symbol_name"], s["start_line"], s["end_line"]) for s in turn["sources"]], flush=True)
                with SessionLocal() as db:
                    for ref in turn["sources"]:
                        chunk = db.scalar(select(CodeChunk).where(CodeChunk.repository_id == repo,
                            CodeChunk.chunk_id == ref["chunk_id"], CodeChunk.commit_sha == ref["commit_sha"]))
                        assert chunk is not None and chunk.content.startswith(ref["content"])
                        assert not ref["file_path"].lower().endswith(".md")
                body = dict(request_id=str(uuid4()), expected_version=turn["version"],
                    answer="I do not know how this implementation works. I cannot explain its purpose or control flow yet.")
                url = base + "/api/interviews/" + turn["session_id"]
                answer = client.post(url + "/answers", json=body)
                print("ANSWER", answer.status_code, flush=True)
                if answer.status_code != 200:
                    print(answer.json(), flush=True)
                    raise RuntimeError("Answer failed")
                updated = answer.json()
                print("DECISION", updated["action"], "FOLLOWUP", updated["question"], "FEEDBACK", updated["feedback"], flush=True)
                assert updated["action"] == "follow_up"
                history = client.get(url)
                assert history.status_code == 200
                assert len(history.json()["turns"]) == 2
                assert history.json()["current"] == updated
                replay = client.post(url + "/answers", json=body)
                assert replay.status_code == 200 and replay.json() == updated
                # Fresh Python process proves history does not depend on API memory.
                probe = subprocess.run([sys.executable, "-c",
                    "from uuid import UUID; from app.db.interviews import load; "
                    + "r=load(UUID('" + turn["session_id"] + "')); "
                    + "assert r['version']==1 and len(r['turns'])==2; print('DURABLE_HISTORY_OK')"],
                    check=True, capture_output=True, text=True, env=env)
                print(probe.stdout.strip(), "REPLAY_OK", "SESSION", turn["session_id"], flush=True)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()

if __name__ == "__main__":
    main()
