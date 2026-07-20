# Contributing

Read `AGENTS.md` first. The short version: keep the core boring, write the failing test first, use synthetic fixtures, and do not weaken provenance/deletion boundaries for convenience.

## Setup

```bash
uv sync --all-packages --dev
uv run pytest
```

## Pull requests

- one coherent change;
- tests prove the behavior and failure mode;
- docs match the commands actually run;
- no real personal data or credentials;
- new connectors implement bootstrap, incremental sync, reconciliation, and deletion semantics.

Architectural changes require an ADR under `docs/adr/`.
