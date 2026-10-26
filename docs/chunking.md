# Phases 3.1–3.2: deterministic hybrid source chunking

`app.services.chunking.chunk_source` accepts decoded source plus repository UUID, repository-relative path and full commit SHA. It performs no fetching, database access, execution, file writes or model calls. The existing ingestion pipeline is unchanged. No tests or runtime checks were run by the agent.

## Contract

The result is a frozen `ChunkingResult(chunks, status, reason)`. Each frozen `CodeChunk` contains:

- `chunk_id`: deterministic SHA-256 of version, repository/path/commit, strategy, symbol, offsets, content and context.
- `repository_id`, `file_path`, `commit_sha`.
- `symbol_name`: qualified name such as `Client.fetch` or `outer.inner`; module remainder is `<module>`.
- `symbol_type`: `module`, `class`, `function`, `async_function`, `method`, `async_method`, or fallback `text`.
- `start_line`, `end_line`: inclusive, one-based source lines.
- `start_offset`, `end_offset`: half-open Unicode-character offsets into LF-normalized source. These disambiguate fragments of one oversized line. CRLF and CR are normalized to LF before parsing/slicing.
- `content`: exact source slice at those offsets; indentation and decorators are retained.
- `context`: bounded excerpts of symbol/enclosing signatures, docstrings and module imports/docstring. It is separate from the source slice and does not change line attribution.
- `strategy`: `ast`, `tree_sitter` or `text`; `chunk_index`: zero-based source ordering. Python and unsupported-language fallback retain `chunker_version=python-ast-v1`; Tree-sitter inputs use `tree-sitter-0.13-v1` (including their text fallback).

Python uses the standard-library AST. Nested definitions are independent symbols. An enclosing class/function emits only its remaining source regions, so method/nested-function bodies are not duplicated inside parent chunks. Module-level imports, assignments, comments and other code remain module chunks. Context excerpts can repeat; source slices do not overlap. Whitespace-only regions are omitted. Chunks and context are retrieval excerpts, not necessarily independently compilable programs or complete dependency closure.

`ChunkingOptions` defaults: `max_chars=4000` (content plus context), `max_lines=100` (content only), `context_chars=600`, `max_chunks=2048`. Context must be at most half the character budget; for example, `ChunkingOptions(max_chars=512, context_chars=128, max_lines=20)`. Limits use characters, not model tokens. Splitting prefers AST statement ends, then line boundaries, then spaces within oversized lines, finally hard character cuts. There is zero source overlap. Stable input/options on Python 3.12 produce stable ordering/IDs; future algorithm changes must bump the version.

The service reuses the existing path validation, file filtering and 200 KiB UTF-8 source cap. AST traversal is bounded to 50,000 nodes. Empty/whitespace-only input returns `empty`. Invalid Unicode, NUL-containing text, excluded files, oversize input and exceeded chunk-count limits return `skipped` with a reason and no partial chunks. Syntax errors or AST complexity limits produce bounded text fallback and an explicit reason; no input source is included in diagnostic messages. Eligible non-Python files (for example JavaScript or Markdown) use the same text fallback with `unsupported_language`. Unknown/excluded extensions remain excluded by the existing allowlist. Fallback assigns `<file>`/`text`, never invented AST symbols. Invalid metadata/options raise `ValueError`.

## Manual PowerShell example

Run from the existing backend. This reads an example source file as data; it never imports or executes it. The UUID and SHA below are illustrative metadata only.

```powershell
cd C:\Users\HP\Desktop\RepoIQ\backend
uv run python -c 'from pathlib import Path; from uuid import UUID; from dataclasses import asdict; import json; from app.services.chunking import chunk_source; from app.schemas.chunking import ChunkingOptions; result = chunk_source(Path("app/services/source_reader.py").read_text(encoding="utf-8"), repository_id=UUID(int=1), file_path="app/services/source_reader.py", commit_sha="a"*40, options=ChunkingOptions(max_chars=512, context_chars=128, max_lines=20)); print(json.dumps(asdict(result), default=str, indent=2))'
```

Expect `status: ok`, module chunks plus `fetch_source_file` and `decode_source_file` symbols, bounded content/context and source line ranges. Repeating unchanged input should print identical IDs. Use the following example file to inspect class, method and async function extraction without changing repository files:

```powershell
$example = New-TemporaryFile
@'
"""Greeting utilities."""
PREFIX = "Hello"

class Greeter:
    """Format a greeting for one user."""
    def greet(self, name):
        return f"{PREFIX}, {name}"

    async def greet_async(self, name):
        return self.greet(name)

async def welcome(name):
    return await Greeter().greet_async(name)
'@ | Set-Content -LiteralPath $example.FullName -Encoding utf8
uv run python -c 'import sys,json; from pathlib import Path; from uuid import UUID; from dataclasses import asdict; from app.services.chunking import chunk_source; result=chunk_source(Path(sys.argv[1]).read_text(encoding="utf-8-sig"), repository_id=UUID(int=1), file_path="example.py", commit_sha="a"*40); print(json.dumps(asdict(result),default=str,indent=2))' $example.FullName
```

Expected symbols include `<module>`, `Greeter`, `Greeter.greet`, `Greeter.greet_async` and `welcome`. The temporary file is created only when the owner runs these commands. No automated tests are created.

Phase 3.1 introduced `backend/app/schemas/chunking.py` and `backend/app/services/chunking/{__init__,python_ast,text}.py`. Phase 3.2 adds `tree_sitter_parser.py`, extends dispatch/schema and shares the existing source partitioner without changing Python output. No migrations, API routes, ingestion changes or stored source files are added.

## Phase 3.2 language selection

Python still uses `ast`, with unchanged behavior and IDs. `.js`/`.jsx` use JavaScript, `.ts` TypeScript, `.tsx` TSX, `.java` Java, and `.cs` C# via `tree-sitter-language-pack==0.13.0`. This pinned release bundles grammars; chunking does not download parsers. Dependencies and native bindings are resolved in `backend/uv.lock`; use `uv sync --locked`. See the [official pinned package API](https://github.com/Goldziher/tree-sitter-language-pack/tree/v0.13.0).

Tree-sitter extracts functions (including arrows), classes, methods, interfaces, explicit constructors and namespaces where represented by those grammars. Named assignments supply names for anonymous expressions; other anonymous symbols use deterministic source positions. Constructors embedded in class signatures remain class context. Unsupported valid constructs remain in enclosing/module source; they are not discarded. Context includes bounded symbol/enclosing headers and import/package/using declarations. All existing size limits, source partitioning, stable-ID generation and fallback splitting are shared. Unicode byte offsets are converted to the existing character-offset contract.

Container headers and closing braces are not emitted as standalone low-value chunks when a class, interface or namespace has extracted children. Their bounded signatures remain in child context. Comments, fields, initializers and any other meaningful container source are still emitted, so only syntax-only remainders are omitted.

The earlier non-Python fallback description now applies only to eligible languages outside this mapping (for example Markdown or Go). Any Tree-sitter error/missing node triggers whole-file bounded text fallback (`tree_sitter_syntax_error`); unavailable bindings, parse failures and traversal limits report `tree_sitter_unavailable`, `tree_sitter_parse_error` and `tree_sitter_node_limit`. No partial AST output is presented as valid. This is structural extraction, not semantic/type analysis. Keep the lockfile for reproducibility; grammar/algorithm upgrades require version review.

Manual PowerShell (illustrative source is parsed, never executed):

```powershell
cd C:\Users\HP\Desktop\RepoIQ\backend
uv sync --locked
uv run --locked python -c 'from uuid import UUID; from app.services.chunking import chunk_source; r=chunk_source("interface User { name: string; } class Greeter { constructor() {} greet(): string { return String(1); } } const twice = (x: number) => x * 2;", repository_id=UUID(int=1), file_path="example.ts", commit_sha="a"*40); print(r.status, r.reason); print([(c.symbol_name,c.symbol_type,c.strategy,c.start_line,c.end_line) for c in r.chunks])'
```

Expect `ok`, `tree_sitter` chunks, and symbols including `User`, `Greeter`, `Greeter.constructor`, `Greeter.greet`, and `twice`. The Python examples above remain applicable. Tests/runtime verification: **NOT RUN — owner handles verification**.

Asaan alfaaz mein: AST code ki banawat parhta hai, usay chalata nahi. Har function/method ka tukra apni file, commit aur line numbers ke saath milta hai.
