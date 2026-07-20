# Life Topography

A private, local-first evidence vault that turns personal data sources into an inspectable, queryable map of people, events, artifacts, and relationships.

> Status: pre-alpha backbone. The repository currently defines the ingestion contract and project architecture. Do not trust it with real personal data yet.

## What this is

Life Topography ingests a bounded historical snapshot from a source, then follows its incremental change stream. It stores immutable source evidence and derives typed observations with provenance. Local agents can query the vault through narrow APIs and MCP tools without receiving database or credential access.

## What this is not

- not a cloud service that uploads your life;
- not an autonomous email agent;
- not a vector database with a chat box;
- not a promise that an LLM "knows" you;
- not production-ready encryption yet.

## Chosen stack

- Python 3.12
- `uv` workspace with separate connector SDK and application packages
- Pydantic contracts
- FastAPI at the HTTP edge
- SQLAlchemy 2 + Alembic + SQLite/FTS5
- Typer CLI
- official Python MCP SDK
- pytest, Ruff, and mypy
- one OCI image and Docker Compose; Tauri sidecar later

The domain and ingestion kernel remain framework-independent so we can harden or replace adapters without rewriting connector contracts.

## Repository layout

```text
packages/sdk/       connector contracts and contract-test helpers
packages/app/       ingestion kernel, persistence, API, CLI, MCP adapters
tests/fixtures/     synthetic cross-package fixtures
docs/adr/           architectural decisions
docs/plans/         executable implementation plans
docker/             image and Compose deployment
```

## Development

```bash
uv sync --all-packages --dev
uv run pytest
uv run ruff check .
uv run mypy packages
```

See `AGENTS.md` before contributing and `docs/plans/` for the current build sequence.

## Privacy contract

Raw personal data stays on the user's host by default. Remote inference, telemetry, full-body retrieval, and embeddings are separate explicit capabilities. Every derived claim must be evidence-backed and deletable through lineage.

## License

Apache-2.0. See `LICENSE`.
