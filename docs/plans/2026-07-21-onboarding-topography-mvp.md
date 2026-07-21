# Onboarding Topography Validation MVP

**Goal:** Let one technical user point the local daemon at a real email `.mbox`, preview the scope, explicitly consent to metadata-only processing, bootstrap a deterministic map, inspect why nodes/edges exist, and delete the vault.

**Validation question:** Does seeing an evidence-backed map of people, organizations, and threads from your own history feel materially more useful than inbox search?

**Technical sweep status (2026-07-21):** the code, packaging, 5,000-message synthetic import, provenance, browser flow, local-only behavior, and physical reset passed. Docker runtime and a repeatable 390px render were unavailable on the validation host, and no personal archive or external tester completed the flow. The implementation is a technical validation candidate; this plan's full completion gate remains open until all acceptance criteria below pass. See the [validation record](../validation/2026-07-21-mvp-validation-sweep.md).

## Product boundary

This is a local, single-user validation build. It is not a general assistant, hosted service, or Gmail OAuth product.

Build:
- local MBOX preview and metadata-only bootstrap;
- resumable/idempotent evidence ingestion;
- deterministic person, organization, and thread topology;
- provenance from every node and edge to source evidence;
- onboarding progress, map exploration, fresh-source import navigation, and full reset;
- synthetic demo path requiring no personal data;
- localhost web UI, CLI workflow, tests, Docker configuration, and CI.

Outstanding in the candidate:
- current-source receipt/status details and an explicit back-to-map action;
- runtime verification of Docker and the final 390px layout;
- personal-archive and external-user acceptance.

Defer:
- Gmail OAuth and push notifications;
- message bodies, attachments, semantic summaries, embeddings, and LLMs;
- financial extraction, commitments, habits, and contact enrichment;
- graph databases, plugin discovery, desktop packaging, multi-user auth;
- cloud telemetry or any data egress.

## Architecture

`MboxConnector` converts approved header fields into source-shaped `EvidenceRecord` objects. It never retains bodies. `IngestionKernel` commits batches and cursors. A deterministic projector rebuilds canonical node/edge tables from evidence, writing explicit evidence links. FastAPI and Typer call the same onboarding service. The browser receives only map projections and the bounded header metadata listed in the consent screen.

For MVP consistency, projections are fully rebuilt after a completed import. This is intentionally less clever and more correct than an incremental projection engine. The source cursor remains resumable so interrupted ingestion can continue.

## Task 1 — MBOX preview and connector contract

**Tests first:**
- preview counts messages, valid/invalid dates, unique addresses, date range, and file size without retaining content;
- headers with encoded names, repeated recipients, missing message IDs/dates, malformed addresses, and reply prefixes normalize deterministically;
- evidence payload contains approved headers only and never body text;
- source IDs remain stable across repeat imports;
- cursor resumes at the next message index.

**Files:** connector module, synthetic MBOX fixture builder, focused tests.

## Task 2 — Topography projection

**Canonical nodes:** `self`, `person`, `organization`, `thread`.

**Canonical edges:** `interacted_with`, `member_of`, `participated_in`.

**Tests first:**
- owner aliases collapse to `self`;
- email addresses normalize case and display names do not control identity;
- common personal email domains do not become organizations;
- reply prefixes collapse to one thread key;
- repeat rebuilds produce identical graph output;
- each node and edge has evidence links;
- deleting evidence and rebuilding removes its derivatives.

**Files:** projection models, SQLite tables/queries, deterministic projector, tests.

## Task 3 — Onboarding application service

**Tests first:**
- preview does not mutate the vault;
- import requires explicit metadata-only consent and owner email;
- job reports queued/running/projecting/completed/failed phases;
- duplicate execution remains idempotent;
- completion returns map counts and source receipt;
- reset deletes evidence, checkpoints, projections, and jobs.

The web path may reference only an explicit file supplied by the local operator. No directory browsing API is exposed. Docker users mount imports read-only at `/imports`.

## Task 4 — Professional local UI

Use server-rendered HTML, vanilla JavaScript, and local static assets. No Node build, CDN fonts, trackers, analytics, gradients, glassmorphism, fake AI chat, or decorative particle soup.

Screens:
1. Welcome and privacy promise.
2. Source selection: synthetic demo or local MBOX path.
3. Scope preview and explicit consent receipt.
4. Import progress with honest phase/count/error state.
5. Topography explorer with list-first overview and restrained SVG map.
6. Evidence drawer showing bounded headers and derivation reason.
7. Settings/reset with destructive confirmation.

Design: near-black graphite surfaces, cool gray type, one desaturated indigo accent, one green status color, 8px rhythm, system font stack, visible keyboard focus, responsive single-column fallback.

## Task 5 — Validation workflow and distribution

- `topography demo` creates/imports an obviously synthetic MBOX and prints the local URL;
- `topography import-mbox PATH --owner EMAIL` supports terminal-first testing;
- Docker Compose persists `/data` and read-only mounts `/imports`;
- README has a five-minute test path and explains exactly what is and is not stored;
- no telemetry; include an optional local feedback export containing product metrics only, never personal values.

## MVP acceptance criteria

Call it a validation MVP only when:

1. A clean checkout reaches a synthetic map in five minutes using documented commands.
2. A real MBOX preview happens before mutation and reports scope accurately.
3. The import can stop and resume without duplicates.
4. Stored evidence contains no message body or attachment bytes.
5. The resulting map shows people, organizations, threads, interaction weight, and time span.
6. Every visible node/edge can explain its deterministic derivation and link to one or more evidence records.
7. Full reset removes evidence, cursors, projections, and onboarding state; tests prove it.
8. UI works at 390px and desktop width, keyboard focus is visible, and empty/error/loading states are intentional.
9. Ruff, strict mypy, tests, package builds, Docker build/health, and CI pass.
10. Three external technical users can complete onboarding without live hand-holding and answer whether the map exposed anything worth returning to.

## Stop condition

Stop feature development after the criteria above. Do not add OAuth, AI, more sources, or richer analytics until users complete onboarding and the topography itself earns repeated use.
