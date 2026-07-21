# Life Topography — privacy-first, self-hosted target architecture

> **Status:** long-term target architecture written before the MBOX validation build. It is not a description of the current implementation. The technical validation candidate uses metadata-only local MBOX import and ordinary SQLite with owner-only permissions; SQLCipher, Gmail OAuth, attachments, MCP, and model features remain deferred. See the [implemented validation sweep](../validation/2026-07-21-mvp-validation-sweep.md) and [next-phase plan](../plans/2026-07-21-post-mvp-validation-plan.md).

**Long-term target decision:** if the deterministic map proves useful, evolve toward a single-user local application with an encrypted SQLite/SQLCipher vault, consent-gated Gmail **metadata-first** connector, deterministic ingestion/indexing, and a local-only query API/UI. Offer an optional local agent through MCP only after the evidence layer earns it. Neither an LLM nor an agent is necessary for retrieval. Raw personal data never leaves the host by default.

This deliberately does **not** start as a generic agent, cloud graph database, vector SaaS, or a large-scale Gmail archive. Those increase the attack surface and make deletion and consent harder without improving the first user outcome: “show me the people, commitments, places, and topics that shaped this time period, with links back to the evidence.”

## 1. Product contract and non-goals

### The target-phase user outcome
For a user-selected Gmail account and date range, build a private, inspectable timeline/map of:

- interactions (thread/date/direction/participants),
- people and organizations inferred from normalized addresses/domains,
- user-approved topics and relationships,
- a confidence-scored “topography” view, where every result can open the exact local source record and its consent/provenance.

### Explicit target-phase limits

- **One human, one vault, one Gmail account; Gmail read-only.** No sending, modifying labels, delegated/domain-wide authority, sharing, collaboration, calendar, location tracking, or social/health/financial connectors.
- Start with Gmail **metadata**, headers, labels, snippets, and thread structure. Full body retrieval/indexing is a separate, per-message or per-query consent action—not a background default.
- No cloud embedding, model, telemetry, crash reporting, analytics, or remote inference by default. A user may explicitly configure a remote provider later, but the request must contain a sanitized derived prompt—not raw messages—unless a separate per-request confirmation allows raw data.
- No autonomous action. The system is read-only in the target phase and never lets an LLM expand scopes, enable a connector, or export data.

## 2. Component decisions

```text
Google Gmail API ──OAuth/connector──> encrypted intake spool ──> normalizer
                                                                  │
UI / local REST API <── query service <── SQLCipher vault <───────┤
       │                         │             │                  ├─ optional local embeddings
       │                         │             │                  └─ edge/topography materializer
       └── localhost MCP server ─ agent harness ─ local small model (optional)
                                             └─ skills = constrained workflows/policy text
```

| Component | Target-phase decision | Why / boundary |
|---|---|---|
| System of record | **SQLite with SQLCipher**, WAL mode, migrations, foreign keys, FTS5. One DB per vault. | A single-user local product needs transactional ingestion, simple backup, portable export, and reliable foreign-key deletion more than distributed scale. Encrypt DB pages; do not mistake an app-level password hash for encryption. |
| Attachments / raw full messages | Separate encrypted object files, content-addressed only by a *keyed* digest; metadata in DB. Default: do not download. | Avoids database bloat and lets a full-body/attachment object be revoked independently. The keyed digest reduces offline correlation across vaults. |
| Connectors | Isolated, capability-declared workers communicating through a local versioned ingestion protocol. Gmail first. | Connector code gets the minimum scoped secret and produces normalized records; it cannot query arbitrary vault data or call models/network services. |
| Search / embeddings | FTS5 and structured SQL first. Optional local embedding model + on-disk HNSW/SQLite vector extension for approved derived text only. | Keyword/date/person queries cover the target phase. Vectors are lossy derived personal data, costly to delete/rebuild, and do not replace evidence. Do not introduce a hosted vector DB. |
| Graph | Relational edge tables and SQL recursive queries/materialized aggregates; no graph DB in the target phase. | `entity`, `edge`, and `observation` tables form a property graph without another authorization/encryption/backup plane. Promote to a graph engine only if multi-hop analytical latency is measured as a problem. |
| Local small model | Optional, downloaded/model-version-pinned local model via llama.cpp/Ollama class runtime. Use only for bounded extraction (topic suggestion, entity alias suggestion, query intent), with schema-constrained output. | The model is an untrusted probabilistic helper. Deterministic normalizers create canonical records; user/evidence gates any model-created relation. A 1–4B quantized model is adequate for suggestions but not a source of truth. |
| MCP | A **localhost-only, authenticated MCP server** exposing narrow read tools (`search_observations`, `get_evidence`, `topography_summary`) and explicit consent/status tools. | MCP is the integration boundary for clients/agents—not the database or policy engine. It returns source IDs/quoted minimised fields, enforces capability scopes and audit events, and has no generic SQL, filesystem, token, or network tool. |
| Agent harness | Thin local orchestrator with an allowlisted tool registry, per-tool schemas, policy checks, budget/time limit, audit trail, and human confirmation boundary. | It may plan a read-only investigation; it cannot bypass connector/consent rules. It should run without a cloud key and use the local model optionally. |
| Skills | Versioned human-readable procedures/prompt templates (e.g., “weekly reflection,” “Gmail import preview”). | Skills are UX/policy guidance, tested fixtures, and tool recipes. They are **not** an access-control mechanism, trusted code, or a replacement for connector and MCP authorization. |

### Deployment profile

- Default: bind UI/API/MCP to Unix socket or `127.0.0.1`; use OS account permissions (`0700` vault directory). If hosted on a personal VPS, place it behind WireGuard/Tailscale or SSH forwarding—not a public reverse proxy in the target phase.
- Run connector, API, and model runner as separate least-privileged processes/users. The connector secret directory is readable only by connector/token broker; the UI/agent never receives refresh tokens.
- Model packages are code/supply-chain inputs: pin checksum/version, show model license and size before download, and support offline import.

## 3. Data lifecycle and minimization

### Ingestion pipeline

1. **Consent preview:** user sees connector name, Google account, precise scopes, fields, date window, retention, and whether full body/attachments are enabled. Persist a versioned consent receipt before sync.
2. **Incremental fetch:** Gmail worker uses a stored cursor/history ID and an explicit query/date range. It retrieves message metadata first; it does not silently backfill all mail.
3. **Normalize deterministically:** canonicalize timestamp, direction, message/thread IDs, participant addresses, label IDs, and a limited subject/snippet. Store sender/recipient addresses only as needed for entity resolution; preserve the original protected value separately from displayed aliases.
4. **Classify locally:** deterministic rules mark likely credentials, medical, financial, legal, or sensitive-personal material. Default action is exclusion from body download, embeddings, and LLM context. Let the user review/override exclusions.
5. **Derive:** create observations, entities, and evidence-linked edges. Embeddings and model suggestions are derived artifacts with an input record set and model version.
6. **Index:** FTS/graph aggregates update in the same DB transaction where possible; vector index writes are journaled and replayable. Until a derivative exists, queries fall back to structured/FTS retrieval.

### Data minimization defaults

| Data class | Default retained | Default excluded / deferred |
|---|---|---|
| Gmail | provider IDs, thread/message relationship, timestamps, participant addresses, label IDs, limited subject/snippet, fetch state | full body, attachments, draft/sent mutation, permanent broad mailbox import |
| Sensitive content | category flag, source ID, and user decision | content in embeddings, agent/model context, exports |
| Contacts/entities | canonical address/domain plus user-editable display label | contact-book merge, public enrichment, speculative identity matching |
| Derived data | only aggregates and provenance needed for view/query | raw hidden content copied into summaries, unlimited conversation transcripts |
| Logs | append-only security/audit events, tool name, actor, data-class/count—not payload | raw OAuth codes/tokens, email bodies, model prompts/responses |

## 4. Security, consent, and governance

### Encryption and secret handling

- Encrypt the vault with SQLCipher (AES-256); create a unique random vault key. Store/wrap it in the platform secret store where available (Linux Secret Service/keyring); require an explicit passphrase-derived key fallback using a memory-hard KDF (Argon2id) with per-vault salt. Configure key rotation as a re-encryption/export-and-reimport job, not a false promise of instant rotation.
- Encrypt attachment objects independently with authenticated encryption (AEAD), unique nonce per object, and a per-object data-encryption key wrapped by the vault key. Backups must be encrypted before leaving the machine.
- Lock memory where practical, redact process arguments/logs, zero temporary plaintext files, set secure permissions, and protect the host/disk. At-rest encryption cannot protect data after an unlocked process or compromised host accesses it.
- OAuth refresh tokens live in the OS secret store or a dedicated encrypted token store; never in the main DB, logs, MCP responses, shell history, or a repository.

### Consent model

Consent is a **versioned, revocable grant**, not a checkbox. A grant binds: connector/account, purpose, field classes, source query/date range, retention, processing modes (storage, FTS, embedding, local model, remote model), and expiry. The policy engine checks it at fetch, derivation, retrieval, export, and agent tool invocation.

- Use just-in-time grants: body access, embeddings, model processing, and any remote call each require their own purpose-limited consent.
- Show an import preview/count estimate and data-class explanation before first sync. Provide pause, scope downgrade, revoke, and “forget this source/range” controls.
- Never silently treat an OAuth grant as permission to use data for unrelated model training, diagnostics, or product analytics.

### Provenance, correction, and deletion

Every displayed claim must resolve to an evidence record. Store immutable source references and transformation lineage; do not overwrite a source observation merely because an extractor improved. Corrections are user-authored overlays that take precedence and retain author/time/reason.

Deletion is a **tombstone + reachability purge** job:

1. revoke/pause the connector and revoke Google token when requested;
2. mark selected source records deleted and make them unavailable immediately;
3. traverse `derivation_input` to invalidate observations, entity inferences, summaries, FTS rows, vector entries, exports, caches, and model-run outputs;
4. physically remove/rebuild affected indexes and encrypted objects; run `VACUUM`/secure storage cleanup according to documented platform limits;
5. retain a minimal non-content deletion receipt (IDs/keyed hashes, time, scope, result) for audit, unless the user selects total vault destruction; and
6. report unresolved external copies (e.g., an export the user saved) honestly—local deletion cannot revoke copied files.

A deletion request must be idempotent, resumable, and expose a job status. Backups need an expiry/rotation policy; otherwise deletion is incomplete.

## 5. Gmail OAuth design

**Scopes and client flow**

- The initial Gmail target needs `https://www.googleapis.com/auth/gmail.metadata` (restricted). Do not request `gmail.readonly` until the user enables full message content, and never request `mail.google.com/`, `gmail.modify`, or `gmail.send` in this target phase. Gmail scope guidance explicitly says to choose the narrowest scope and notes that Gmail scopes can be restricted.
- Use an OAuth **Desktop app** client for a client-side deployment. Launch the system browser; use Authorization Code with PKCE (S256), a random validated `state`, and an installed-app loopback redirect as Google documents. Do not embed a browser/webview or use the deprecated out-of-band flow.
- Request scopes incrementally at the feature that needs them. Display the exact account and scopes. If token refresh fails/revocation occurs, stop sync and require new consent—never retry with broader scope.
- A public product using restricted Gmail scopes must plan for Google OAuth verification/security assessment requirements before broad distribution. For a personal/testing deployment, configure the consent screen/test users correctly; this does not erase the obligation when publishing.
- Token broker owns offline refresh token. Encrypt at rest, rotate/revoke on disconnect, use least-privilege file permissions, and never return it through MCP. Consider DPoP for refresh-token sender constraint where the chosen client/library supports it.

## 6. Post-validation target phase: services, acceptance criteria, and deferrals

### Services

1. **Vault service:** migrations, SQLCipher open/lock/backup, object encryption, provenance/deletion worker.
2. **Gmail metadata connector:** OAuth PKCE, scope/status page, date/query bounded incremental import, account disconnect/revoke.
3. **Topography service/UI:** timeline, people/domain/topic views; filters; evidence drawer; data/consent/deletion dashboard.
4. **Indexer:** deterministic people/domain/thread edges; FTS5 over approved subject/snippet; optional *off by default* local embeddings only after a per-vault consent grant.
5. **Local MCP read server:** Unix socket/loopback, bearer/session authentication, three read tools, consent/status tool, audit records. The same API powers UI and MCP, so policy is not duplicated.

### Acceptance criteria

- A new vault can be created/locked/unlocked, and its database plus any raw objects are unreadable without the vault key.
- User can consent to exactly `gmail.metadata` and import a chosen date range; the UI clearly shows account, fields, last cursor, scope, and record count.
- A query can show a person/thread/time view with every generated relationship linked to source evidence and confidence/method.
- With embeddings and local model disabled, core product functions work fully offline after sync.
- “Forget a message/thread/date range” immediately suppresses it and completes an auditable derivation/index purge; disconnect revokes token and blocks future sync.
- Network egress test proves that, after OAuth/sync, no raw mail is sent to any non-Google endpoint by default.

### Not in the target phase

Full-body/attachment corpus, additional connectors, write actions, public internet hosting, multi-user tenancy, realtime push/webhooks, cross-device sync, cloud LLMs/vector stores, automatic life conclusions, and graph-database migration.

## 7. Concrete relational data model

All tables include `id` (UUIDv7), `created_at`, `updated_at`; sensitive source/derived content is encrypted in the vault. `*_id` fields are foreign keys; foreign keys are enforced.

```sql
-- Vault/policy
vault(id, schema_version, key_version, locked_at)
connector(id, kind, version, capability_manifest_json, status)
connection(id, connector_id, account_pseudonym, token_ref, sync_cursor_encrypted,
           status, last_sync_at)
consent_grant(id, connection_id, purpose, field_classes_json, source_filter_json,
              processing_modes_json, granted_at, expires_at, revoked_at, receipt_json)
policy_decision(id, consent_grant_id, action, subject_type, subject_id, allowed,
                reason_code, decided_at)

-- Source records: provider identifiers are encrypted; display/search helpers are minimal.
source_record(id, connection_id, provider_kind, provider_id_encrypted,
              provider_parent_id_encrypted, captured_at, occurred_at,
              content_class, payload_ciphertext_ref, content_state, deleted_at)
message_metadata(source_record_id PK/FK, thread_source_id, direction,
                 subject_ciphertext, snippet_ciphertext, label_ids_json,
                 header_fingerprint_keyed)
participant(id, normalized_address_ciphertext, address_keyed_hash, domain_keyed_hash,
            display_name_ciphertext, sensitivity)
record_participant(source_record_id, participant_id, role, ordinal)

-- Evidence-led canonical meaning; one source can yield many observations.
entity(id, entity_type, canonical_key_ciphertext, canonical_keyed_hash,
       display_name_ciphertext, user_verified, sensitivity, merged_into_id)
entity_alias(id, entity_id, alias_ciphertext, alias_keyed_hash, source, confidence)
observation(id, kind, occurred_at, value_ciphertext, confidence, method,
            status, user_override)
evidence(id, observation_id, source_record_id, locator_json, excerpt_ciphertext,
         evidence_role, confidence)
edge(id, from_entity_id, to_entity_id, relation_type, valid_from, valid_to,
     weight, confidence, method, status)
edge_evidence(edge_id, evidence_id)

-- Derived artifacts and deletion reachability.
derivation(id, kind, producer, producer_version, config_hash, status, created_at)
derivation_input(derivation_id, input_type, input_id, input_revision)
derivation_output(derivation_id, output_type, output_id)
embedding(id, subject_type, subject_id, model_id, model_hash, vector_ref,
          consent_grant_id, derivation_id, deleted_at)
export_receipt(id, selection_json, destination_class, created_at, expires_at,
               derivation_id)
delete_job(id, request_json, requested_at, completed_at, status, result_json)
audit_event(id, actor_type, actor_id, action, object_type, object_id,
            data_class, count, outcome, occurred_at, prev_event_hash, event_hash)
```

**Key invariants**

- `evidence.source_record_id` is mandatory for machine-created observations/edges; user-authored corrections use a distinct `method='user'` and cannot masquerade as source evidence.
- Any `embedding`, summary, model output, edge, or export must have a `derivation` record; `derivation_input` makes deletion traversal possible.
- Pseudonymous/keyed hashes facilitate matching inside one vault only; never use unsalted global email hashes or vendor telemetry identifiers.
- `audit_event` payloads contain IDs/classes/counts, not content. Hash chaining signals tampering but is not a substitute for host security or an external immutable audit log.

## 8. Ingestion mode: bootstrap snapshot + continuous change feed

Topography only becomes valuable when it has enough historical context to establish a baseline **and** stays current without repeated manual imports. Each connector therefore implements two explicitly separate modes against the same evidence/provenance contract.

### A. Onboarding bootstrap — a staged, resumable historical snapshot

Do not make onboarding a blind “download your whole life” button. It is a source-by-source import plan:

1. **Discovery preview:** show the account/source, accessible date span, estimated count/size, requested fields/scopes, sensitivity estimate, retention, and expected local storage.
2. **User-selected history boundary:** default to a useful bounded period or selected categories, never an irreversible universal archive by surprise. Full content/attachments remain separately opted in.
3. **Resumable paged import:** persist signed/checkpointed cursors, idempotency keys, connector/parser versions, and per-record state. An interrupted import resumes safely without duplicate entities or evidence.
4. **Progressive materialization:** ingest immutable evidence first; build deterministic entities/events/edges incrementally; only run optional embeddings/models after the source snapshot is stable and consent allows it.
5. **Reconciliation pass:** identify source deletion, edits, missing pages, duplicate identities, and uncertain matches. Never silently overwrite old derived claims; supersede them with provenance.
6. **Completion receipt:** display imported boundaries/counts, exclusions, processing modes, failures, and how to widen, pause, or completely forget the import.

The initial snapshot is a **baseline**, not a one-time truth. Source state, connector version, and policy grant are retained so the system can explain the resulting topography later.

### B. Continuous synchronization — event-oriented and health-visible

After the bootstrap succeeds, a connector maintains a narrow change feed using the source’s safest supported mechanism: provider events/webhooks where available, otherwise bounded incremental cursors/polling. The connector must:

- record every sync cursor/event atomically with processed evidence;
- coalesce repeated changes, deduplicate events, and tolerate provider re-delivery/out-of-order delivery;
- retrieve only changed records, respecting the current consent grant and scope;
- run the same normalizer/derivation path as the historical import—no separate “realtime” data model;
- surface sync freshness, last successful checkpoint, lag, quota/rate-limit state, errors, and required re-authentication in the UI;
- pause immediately when consent expires, a token is revoked, or the local vault is locked;
- support a user-triggered reconciliation scan, rather than pretending event streams are perfect.

For Gmail specifically, bootstrap via a bounded paged history/import and then advance through the provider’s incremental history/change mechanism; treat notification delivery as a hint to sync, not proof that an update was safely processed. Persist the committed cursor only after the corresponding source records and audit events are durable.

**Product implication:** onboarding produces the first compelling “map of this period”; continuous synchronization turns it into a living personal context layer. New connectors must implement both modes before they are considered complete.

## 9. Build sequence

1. Vault/key manager + schema/migrations + encrypted backup/restore test.
2. Consent/policy engine and audit log; write deletion traversal tests before adding indexes/models.
3. Gmail desktop OAuth + metadata-only bounded sync; token broker and disconnect/revoke.
4. Deterministic entities/thread/person/domain edges, FTS, evidence UI, and no-LLM topography views.
5. Local MCP read surface and hardened agent harness.
6. Optional local embeddings, then constrained local-model suggestions behind explicit consent and an evaluation set measuring extraction accuracy, evidence coverage, deletion completeness, and raw-data egress.

## 9. Evidence and design references (accessed 2026-07-20)

1. [Google: OAuth 2.0 for iOS & Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app) — installed apps use a system browser and local redirect; Google documents the installed-app authorization flow.
2. [Google: OAuth authorization best practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices) — secure token storage, PKCE recommendation for desktop apps, `state` validation, incremental authorization, revocation handling, and DPoP support considerations.
3. [Google: Choose Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes) — scope minimization guidance, scope sensitivity/restriction classification, and public-app verification notice.
4. [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html) — authenticated encryption, key-management separation, and avoiding plaintext sensitive storage.
5. [NIST SP 800-57 Part 1 Rev. 5](https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final) — key-management lifecycle principles. Use it as a security baseline, while validating library/platform-specific implementation details.

**Decision gate after the target phase:** measure whether FTS + relational graph meets target latency/quality on a representative private fixture set. Add a dedicated vector or graph database only when those measurements, rather than architecture fashion, justify a new encrypted stateful service.

