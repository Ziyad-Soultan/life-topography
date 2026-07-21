# Life Topography

A private, local-first evidence map for personal history.

Life Topography turns a bounded email export into an inspectable map of the people, organizations, and threads that shaped a period of your life. Every node and relationship links back to the header records that created it. No cloud account, remote model, or inbox permission is required.

> **Status: technical validation candidate, ready for bounded personal-data testing.** The MBOX onboarding flow, deterministic map, provenance drill-down, resumable import, and full vault reset work. Docker runtime, final narrow-screen verification, personal usefulness, and external-user acceptance remain open. The SQLite vault is **not application-level encrypted yet**. Use synthetic data or an encrypted host disk.

See the [full MVP validation sweep](docs/validation/2026-07-21-mvp-validation-sweep.md) for measured results and known gaps, and the [post-MVP validation plan](docs/plans/2026-07-21-post-mvp-validation-plan.md) for the next decision gates.

## See it in one minute

```bash
uv sync --all-packages --dev
uv run topography demo
uv run topography serve
```

Open `http://127.0.0.1:8787`.

The demo creates a fictional 30-message MBOX and sends it through the exact same connector, evidence, checkpoint, and projection pipeline as a real import.

## Try your own email export

1. Export email as a local `.mbox` file. Google Takeout, Thunderbird, and many mail clients support this format.
2. Start the local interface:

   ```bash
   uv run topography serve
   ```

3. Open `http://127.0.0.1:8787`, enter the local MBOX path and your primary email, then review the scope preview.
4. Confirm metadata-only processing and build the map.

You can also import from the terminal:

```bash
uv run topography import-mbox "/path/to/All mail.mbox" \
  --owner-email you@example.com \
  --i-understand-metadata-only
uv run topography serve
```

### What is retained

- sender and recipient addresses;
- display names;
- message date;
- subject and normalized thread key;
- message ID;
- source identity and import cursor.

### What is not retained

- message bodies;
- attachments;
- OAuth credentials;
- embeddings;
- model-generated claims;
- telemetry or remote analytics.

## What the MVP proves

```text
local MBOX
→ scope preview and explicit consent
→ metadata-only immutable evidence
→ resumable, idempotent ingestion
→ deterministic people / organization / thread projection
→ ranked summaries and relationship map
→ per-object evidence drill-down
→ complete evidence + derivative deletion
```

The map is deliberately deterministic. No AI is required to produce it, and SQLite—not the visualization—is the local system of record.

## Docker

Expose the app on loopback and mount an import directory read-only:

```bash
TOPOGRAPHY_IMPORTS=/absolute/path/to/exports \
  docker compose -f docker/compose.yaml up --build
```

Then open `http://127.0.0.1:8787` and use `/imports/your-file.mbox` as the source path.

The Compose stack persists `/data/vault.db` in a named volume, confines browser-requested imports to `/imports`, and never exposes the HTTP service beyond loopback by default. Outside Docker, the browser service accepts paths under the current user's home directory or the configured database directory. Set `TOPOGRAPHY_IMPORT_ROOTS` to a colon-separated allowlist to narrow that further. Direct CLI imports remain an explicit operator action and may read the path supplied on the command line.

## Product boundaries

This is:

- a local evidence vault and deterministic topography;
- a consent-bounded historical bootstrap;
- an inspectable foundation for future incremental connectors;
- an open-source validation surface.

This is not:

- an autonomous email agent;
- a graph database with decorative edges;
- a vector database with a chat box;
- a claim that an LLM “knows” you;
- production-ready encrypted storage;
- a reason to grant broad Gmail OAuth access before the map proves useful.

## Architecture

- Python 3.12
- `uv` workspace with two distributions: connector SDK and application
- Pydantic connector contracts
- FastAPI HTTP boundary
- SQLAlchemy 2 + SQLite with WAL, foreign keys, and owner-only vault file permissions
- Typer CLI
- vanilla HTML/CSS/JavaScript UI with no CDN or build step
- pytest, Ruff, strict mypy
- one OCI image and Docker Compose

The canonical object vocabulary remains `Evidence`, `Observation`, `Entity`, `Event`, `Relationship`, `Artifact`, and `Derivation`. The validation MVP currently projects evidence into people, organizations, threads, and typed relationships; broader canonical objects are deferred until a real second use case earns them.

## Development

```bash
uv sync --all-packages --dev
uv run ruff format --check .
uv run ruff check .
uv run mypy packages
uv run pytest -q
uv build --all-packages
```

See `AGENTS.md` before contributing, `docs/validation/` for observed results, and `docs/plans/` for decision records and implementation sequences.

## Validation questions

The MVP is successful only if testers can answer “yes” to most of these:

1. Did the first map reveal a useful person, organization, or thread pattern quickly?
2. Could you understand why every displayed connection existed?
3. Did metadata-only processing feel proportionate to the value?
4. Was local MBOX export acceptable for an early privacy-first product?
5. Would you return after incremental synchronization exists?
6. Did erase/reset behave exactly as expected?

## License

Apache-2.0. See `LICENSE`.
