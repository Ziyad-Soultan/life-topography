# ADR 0001: Python modular monolith and two-package workspace

- Status: accepted
- Date: 2026-07-20

## Context

The project needs unusually strong ingestion correctness while remaining easy for open-source contributors to extend with connectors. It must run on laptops and small VPS hosts, expose local HTTP/CLI/MCP surfaces, package cleanly in Docker, and leave room for a future Tauri desktop wrapper.

## Decision

Use a Python 3.12 modular monolith in one `uv` workspace with two distributions:

1. `life-topography-sdk`: framework-independent Pydantic contracts, connector Protocols, capability manifests, cursor/batch models, and contract-test helpers.
2. `life-topography`: application services, persistence, migrations, API, CLI, MCP adapters, and built-in connectors.

Use FastAPI only at the HTTP edge, SQLAlchemy 2 and Alembic for persistence/migrations, SQLite WAL/FTS5 with one application-owned writer, Typer for CLI, and the official Python MCP SDK. Build one non-root OCI image. A future Tauri shell may launch the packaged service as a sidecar.

SQLCipher is a storage capability, not a mandatory first-install dependency. The pre-alpha must state clearly that ordinary SQLite is not encrypted. Production-readiness requires tested encrypted builds or an equally credible vault encryption design.

## Why not Rust first?

Rust would improve static guarantees, memory control, and single-binary packaging. It would also raise connector contribution friction, slow iteration while the data contract is still changing, and fragment Python-heavy extraction/model tooling. We can move hardened boundaries later if measured need justifies it; the connector protocol and application boundaries are designed to survive that refactor.

## Why not TypeScript first?

TypeScript would align with a future UI and has a strong MCP ecosystem. Python is materially better for source parsing, local ML, data tooling, and the likely connector contributor base. Tauri keeps the UI decision independent.

## Why SQLite?

The first deployment is one user, one vault, one writer. SQLite gives transactions, portability, backup simplicity, FTS5, and a tiny operational footprint. A graph database, broker, or PostgreSQL would add stateful services before measured workload requires them.

## Consequences

- Async is used at network boundaries; database writes remain serialized and transactionally explicit.
- The SDK cannot import application frameworks.
- MCP/HTTP/CLI call the same application services.
- External connectors can later use Python entry points, but dynamic installation is deferred.
- The lockfile, not optimistic version prose, defines reproducible dependencies.

## Sources considered

- uv Docker guidance: https://docs.astral.sh/uv/guides/integration/docker/
- FastAPI container guidance: https://fastapi.tiangolo.com/deployment/docker/
- MCP server guide and Python SDK: https://modelcontextprotocol.io/docs/develop/build-server
- PyPA plugin discovery: https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/
- Tauri sidecars: https://v2.tauri.app/develop/sidecar/
- SQLite WAL: https://sqlite.org/wal.html
- ActivityWatch local-first precedent: https://github.com/ActivityWatch/activitywatch
