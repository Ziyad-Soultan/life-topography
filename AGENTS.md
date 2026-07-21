# AGENTS.md

## Mission

Build a private, local-first topography of a person's life from evidence they control.

The product is the ingestion kernel: resumable historical bootstrap, continuous change capture, deterministic normalization, provenance, correction, and complete deletion. AI is an optional interpreter. It is never the system of record.

## Taste

- Evidence over vibes.
- Boring infrastructure over fashionable infrastructure.
- One obvious path over five configurable paths.
- Small typed interfaces over framework-shaped domain code.
- Explicit consent over clever automation.
- Local and inspectable by default. Network egress is a feature, never an accident.
- Useful without an LLM. Better with one, never dependent on one.
- Source-specific truth enters once; canonical meaning is derived and rebuildable.
- Delete means source evidence and every reachable derivative, not "hidden from the UI."
- A connector that cannot resume, reconcile, explain, and forget is not done.

## Non-negotiable invariants

1. Raw evidence is immutable. Corrections supersede; they do not rewrite history.
2. Every machine-created claim points to evidence and a versioned derivation.
3. Checkpoints advance only in the same successful commit as their evidence.
4. Ingestion is idempotent. Provider retries and duplicate events are normal.
5. Connector credentials never enter domain models, logs, MCP results, or fixtures.
6. The core works with SQLite, FTS, and deterministic code before vectors or models.
7. Only one process owns database writes in the SQLite deployment.
8. MCP exposes narrow application capabilities, never SQL, filesystem, or tokens.
9. Loopback is the default network boundary. Public exposure requires explicit auth.
10. No source gets a bespoke shadow architecture. Bootstrap and live sync use the same pipeline.

## Current product boundary

Build now:
- local MBOX preview and metadata-only bootstrap;
- deterministic person, organization, and thread projections;
- provenance and full derivative deletion;
- onboarding progress and a restrained localhost map UI;
- synthetic demo data and terminal-first import workflow;
- Docker/Compose and boring CI.

Do not build yet:
- Gmail OAuth, message bodies, attachments, or cloud sync;
- graph database, message broker, Kubernetes, or distributed workers;
- custom model training, summaries, or mandatory embeddings;
- autonomous writes to external systems;
- multi-user tenancy or public internet hosting;
- dynamic plugin marketplace or additional source connectors.

## Architecture boundaries

`packages/sdk` owns stable connector-facing contracts and test helpers. It must not import FastAPI, SQLAlchemy, MCP, or app internals.

`packages/app` owns orchestration, policy, persistence, API, CLI, and MCP adapters. Domain/application services must not import transport frameworks. Adapters call application services; frameworks stay at the edge.

Connectors emit source-shaped evidence plus explicit metadata. The core creates canonical observations/entities/events through versioned derivations. Do not smuggle canonical guesses into raw evidence.

## Agent workflow

1. Read this file, the relevant ADR, and the plan before editing.
2. State the invariant affected by the change.
3. For behavior changes, write one failing test and run it. Confirm the failure is about missing behavior.
4. Write the smallest implementation that passes.
5. Run the focused test, then the full quality gate.
6. Update docs when commands, boundaries, or guarantees change.
7. Commit one coherent change. Do not mix cleanup with behavior.

If a requirement is ambiguous, prefer the smaller reversible design. Record meaningful decisions in `docs/adr/`; do not bury architecture in chat transcripts.

## Quality gate

```bash
uv sync --all-packages --dev
uv run ruff format --check .
uv run ruff check .
uv run mypy packages
uv run pytest
```

For container-facing changes, also build the image and run the documented health check. Never claim Docker verification when Docker is unavailable.

## Security reminders

- No real personal data in tests, examples, screenshots, or issue templates.
- Fixtures are synthetic and obviously fake.
- Never print OAuth codes, refresh tokens, message bodies, model prompts, or vault keys.
- Hashes of email addresses are still personal data; use per-vault keyed hashes.
- Treat embeddings, thumbnails, summaries, indexes, and model outputs as deletable derivatives.
- Do not weaken a boundary merely because an agent or UI is "local."

## Anti-bloat reminders

- No abstraction without two real implementations or a hard boundary requiring it.
- No base class where a Protocol and a small function suffice.
- No generic event bus for an in-process call.
- No repository pattern that merely renames SQLAlchemy.
- No configuration option without a user who needs it now.
- Comments explain why, invariants, and traps—not what the code already says.
- Prefer deleting code to preserving speculative flexibility.

## Definition of done

A change is done when behavior is tested, failure modes are explicit, docs match reality, secrets stay out, deletion/provenance implications are handled, and the simplest user path still works.
