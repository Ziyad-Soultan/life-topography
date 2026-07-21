# Post-MVP validation plan

**Status:** proposed after the 2026-07-21 technical sweep  
**Principle:** validate the map before expanding the ingestion surface.

## Current position

The technical sweep is complete, and the candidate is ready for a bounded single-user archive under the documented encrypted-host threat model. It is not yet an accepted MVP or a product-validated build because Docker, final narrow-screen verification, a personal archive, and external testers remain open.

The next phase should reduce uncertainty in this order:

1. Is the map recognizable and useful?
2. What deterministic corrections make it trustworthy?
3. Is MBOX friction tolerable for validation?
4. Does automatic freshness justify Gmail OAuth complexity?
5. Only then: can optional local intelligence improve interpretation without becoming the system of record?

## Phase 0 — Founder personal-data pilot

**Timebox:** one session; no new features first.

- Export a bounded 6–24 month MBOX.
- Run preview/import/evidence/reset using the documented protocol.
- Capture the eight validation scores in the Obsidian project note.
- Record the first five wrong/noisy objects and the first three useful surprises.
- Measure preview time, import time, map counts, and vault size without recording personal values in Git.

**Exit gate:** a recognizable map plus at least one useful surprise and stated return intent.

If this gate fails, fix projection quality or narrow the product claim. Do not build OAuth.

## Phase 1 — Trust and correction loop

Build only the corrections observed in real use:

1. **Source/status page**
   - current source receipt and parser version;
   - last import and counts;
   - warnings and invalid dates;
   - re-import/add-source/back-to-map actions.
2. **Noise controls**
   - hide/mute automated senders and domains;
   - optionally exclude common notification/list patterns;
   - every exclusion reversible and visible.
3. **Identity corrections**
   - rename a person;
   - merge aliases;
   - mark “not a person”;
   - preserve source evidence and store correction overlays.
4. **Simple map filters**
   - date range;
   - node type;
   - minimum activity;
   - deterministic search.
5. **Validation receipt**
   - local-only export of counts, timings, scores, and issue categories;
   - never export addresses, subjects, names, or evidence IDs by default.

**Exit gate:** the owner can correct the obvious topography errors without editing SQLite or re-exporting mail.

## Phase 2 — Storage posture decision

Before inviting broader real-data testing, choose one:

### Option A — Host-encryption pilot

Keep ordinary SQLite, require BitLocker/LUKS/FileVault or an encrypted VM/storage pool, and state the threat model plainly.

- Fastest path to learning.
- Protects data at rest when the host is off.
- Does not protect an unlocked or compromised host.

### Option B — Application-level encrypted vault

Implement SQLCipher/key management, lock/unlock UX, encrypted backups, and key-loss behavior before broader testing.

- Stronger portable-vault story.
- Adds packaging and key-recovery complexity.
- Should not be confused with protection from a compromised running process.

**Recommendation:** use Option A for the founder pilot. Choose Option B before external testers or portable backups unless every tester already has verified full-disk encryption.

## Phase 3 — Freshness connector, only after value

If the owner says “I would use this if it stayed current,” build Gmail metadata synchronization:

- Desktop OAuth + PKCE;
- narrowest viable metadata/read-only scope;
- token in OS secret storage, never SQLite/logs;
- bounded initial query/date range;
- incremental history cursor;
- source reconciliation and visible health;
- disconnect/revoke and source-scoped deletion;
- same evidence/projector path as MBOX.

Do not add message bodies, sending, labels, or cloud inference.

**Exit gate:** one click keeps a useful corrected map fresh without broadening the privacy boundary.

## Phase 4 — Optional intelligence

Only after the deterministic map and corrections have value:

- local topic suggestions from user-approved fields;
- alias/entity suggestions;
- bounded period summaries with explicit evidence links;
- model/version/config recorded as derivation;
- all outputs deletable and rebuildable;
- no raw data to remote providers by default.

An LLM proposes; the vault and evidence remain authoritative.

## Performance gates

Keep the full deterministic rebuild until measurements fail one of these:

- preview > 10 seconds for the founder archive;
- first map > 60 seconds;
- no-op refresh > 10 seconds;
- peak memory > 1 GB;
- browser interaction becomes visibly blocked.

When a gate fails, profile before redesigning. Likely first optimizations are streaming projection inputs, incremental aggregate replacement, and avoiding full evidence deserialization—not a graph database.

## Decisions required from the owner

1. Which bounded period should the first archive cover: 6 months, 12 months, 24 months, or all mail?
2. Is the test host protected by full-disk/encrypted-dataset storage, or should the vault remain temporary and be erased after each session?
3. What is the first product question: people who shaped an era, career/project contexts, neglected relationships, or a general communication map?
4. Is MBOX acceptable for 3–5 validation sessions, or is Gmail OAuth required before you would genuinely reuse it?
5. After the first map, which correction matters most: hide noise, merge aliases, rename people, or filter by date?
6. Should the next release optimize for founder-only learning or external technical testers?

## Explicit kill list

Until the personal pilot passes:

- no graph database;
- no vector database;
- no body/attachment ingestion;
- no cloud LLM;
- no generic plugin system;
- no public hosting;
- no multiple connectors;
- no dashboard analytics beyond local validation measurements.
