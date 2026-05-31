# ARCHITECTURE.md

Contributor guide for the `perplexity-cli` source. For *using* the installed
tool, see `AGENTS.md` (which `CLAUDE.md` and `GEMINI.md` symlink to) — that file
is a usage reference bundled as an agent skill and should stay free of
development/internals content.

## Environment & Common Commands

Python ≥ 3.12. Dependencies are managed with `uv` (`uv.lock` is committed).

```bash
uv sync                      # create .venv and install deps from the lockfile
uv run perplexity-cli ...    # run the CLI from source without installing
uv pip install -e .          # editable install into the active env

# Build the distributable wheel (hatchling backend)
uv build                     # outputs to dist/

# At least one key must be set for the CLI to run
export PERPLEXITY_API_KEY="pplx-..."     # primary backend
export OPENROUTER_API_KEY="sk-or-v1-..." # fallback backend (also works standalone)
```

**Tests:** run with `uv run --group dev pytest` (suite lives in `tests/`).
Coverage: `uv run --group dev pytest --cov=perplexity_cli --cov-report=term-missing`.
`pytest` / `pytest-cov` are the only dev-group dependencies; there is still no
configured linter or formatter (the global black / ruff rules apply if you add
them, but nothing is wired up). `providers.py` is largely uncovered because it
is real API I/O — exercise it with mocked transports, not live calls.

**Debugging:** set `PERPLEXITY_CLI_DEBUG=1` to make the top-level error handler
re-raise instead of swallowing unexpected exceptions into an exit-70 message
(`main.py:handle_errors`).

## Architecture

The package is a thin Typer CLI over a provider abstraction. Data flows:

```
CLI args / --json / stdin
  → merge_json_with_cli()  (models.py)   validate into a Pydantic *Input model
  → get_provider()         (client.py)   pick backend from available keys
  → Provider.search/ask/chat_stream      (providers.py) call the API
  → *Output model                        (models.py) normalized result
  → render() / render_streaming_chunk()  (output.py) JSON | pretty | text
```

### Modules

- **`main.py`** — Typer app, the `search`/`ask`/`chat` commands, the global
  `@app.callback`, and the `handle_errors` decorator. Global state (`OutputFormat`,
  api key, loaded `Config`) lives on `ctx.obj` (a `State` instance) set by the
  callback.
- **`client.py`** — `resolve_keys()` applies the key precedence chain;
  `get_provider()` uses it to pick which backend(s) to construct.
- **`config.py`** — XDG-aware `config_path()`, the frozen `Config` model
  (`extra="forbid"`), `load_config()`, and the `ask_defaults()`/`search_defaults()`
  mappers that translate config field names to `*Input` field names.
- **`providers.py`** — the `Provider` Protocol and its three implementations.
- **`models.py`** — Pydantic input/output schemas and `merge_json_with_cli`.
- **`output.py`** — `resolve_output_format()` plus renderers for `*Output`
  models to stdout/stderr per format.

### Settings precedence (config file)

A global config file (`config.py`, loaded once in the callback) is the
**lowest-priority** source for every setting. The chain is
`CLI flag > env var > config file > built-in default`, implemented across three
seams so each layer stays testable in isolation:

- **API keys** → `client.resolve_keys()`: `--api-key`/env, then config fallback.
- **`model` + search params** → `merge_json_with_cli(..., config_defaults=...)`:
  config seeds the base dict, JSON overrides it, non-`None` CLI flags win.
- **Output format** → `output.resolve_output_format()`: `--text`/`--pretty`,
  then config `output`, then JSON default.

A broken config raises `json.JSONDecodeError` / `ValidationError`, caught in the
callback and rendered as exit 4 (matching `handle_errors`). The callback derives
its error-reporting format from flags alone, since the config may be the thing
that failed to load.

### Provider abstraction (`providers.py`)

`Provider` is a `typing.Protocol` with `search`, `ask`, and `chat_stream`.
Three implementations:

- **`PerplexityProvider`** — wraps the official `perplexity` SDK.
- **`OpenRouterProvider`** — raw `httpx` against OpenRouter's `/chat/completions`,
  routing bare model names to `perplexity/<model>`. Raw httpx is used deliberately
  (not the OpenRouter SDK) so Perplexity-specific body knobs
  (`search_recency_filter`, `search_domain_filter`, `search_mode`,
  `reasoning_effort`) survive serialization.
- **`FallbackProvider`** — wraps a primary + fallback; retries on the fallback
  when `_should_fallback(exc)` is true (Perplexity status codes in
  `_FALLBACK_STATUS_CODES`, the listed SDK exception types, or any
  `httpx.HTTPError`).

Streaming is normalized through `StreamEvent` (frozen dataclass:
`content_delta`, `citations`, `usage`). Citations are emitted as the full
cumulative tuple only on the chunk where they change; usage only on the chunk
that carries it.

### Key invariants when changing code

- **Global flags (`--text`, `--pretty`, `--api-key`) attach to the root callback,
  not subcommands** — they must precede the subcommand. Keep them on
  `@app.callback`, not on individual `@app.command` functions.
- **Streaming output split:** in `chat`, text mode streams tokens to **stdout**;
  JSON/pretty mode streams tokens to **stderr** so stdout stays clean for the
  final JSON object (`output.render_streaming_chunk`). Preserve this — agents
  rely on `2>/dev/null` to capture clean JSON.
- **Streaming fallback only fires before the first chunk emits**
  (`FallbackProvider.chat_stream`). Once bytes hit stdout, a mid-stream error
  must propagate rather than restart, or output duplicates.
- **OpenRouter path limitations:** `search` is emulated via a `sonar-pro` chat
  completion with OpenRouter's web-search plugin enabled, so `snippet` is
  populated (from each citation's `content`) but `date` is always `null`;
  `related_questions` is always `[]`. The plugin adds a per-search cost. The JSON
  output *schema* stays identical across backends — keep it that way.
- **Exit codes are part of the contract** (see the table in `AGENTS.md`).
  `handle_errors` maps exception types/status codes to codes 2/3/4/5/70/130;
  update both the handler and the `AGENTS.md` table together.
- **Input merge precedence:** `merge_json_with_cli` takes JSON as the base and
  overlays only non-`None` CLI kwargs, then validates. New CLI options must pass
  `None` as their default to participate correctly.
