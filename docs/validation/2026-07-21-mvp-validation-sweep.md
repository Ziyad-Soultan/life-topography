# Validation MVP sweep — 2026-07-21

## Verdict

**Technical candidate ready for bounded single-user personal-data validation on a local encrypted host. Not yet an accepted MVP or a product-validated build.**

The implementation satisfies the technical core of the validation MVP: preview before mutation, explicit metadata-only consent, resumable/idempotent MBOX ingestion, deterministic topography, node and relationship provenance, local-only runtime behavior, and physically verified vault reset.

The next milestone is not another connector or an AI layer. It is one real archive and a structured answer to: **does this map reveal something recognizable and useful enough to revisit?**

## Scope and revision

- Base revision: `92d9161` (`main` after PR #1)
- Runtime: Python 3.12, installed workspace and clean wheel environment
- Browser: packaged wheel served on loopback
- Corpus: deterministic synthetic MBOX with 5,000 physical messages
- Edge cases: duplicate IDs, missing IDs, invalid/missing dates, encoded names, reply/reference headers, personal domains, organization domains, bodies, and attachments
- Personal archive: **not tested; no MBOX/Takeout/EML was available in the validation environment or staging share**
- Docker: **not tested; Docker and Podman are unavailable on this host**
- True 390px runtime: **not repeated; the remote browser driver cannot resize and no local browser binary is installed**

No personal values were copied into the repository, report, fixtures, screenshots, or command output.

## Results

| Area | Result | Evidence |
|---|---|---|
| Formatting and lint | Pass | Ruff format/check clean |
| Static typing | Pass | strict mypy clean across 33 source files |
| Automated tests | Pass | 39 passed |
| JavaScript syntax | Pass | `node --check` |
| Packaging | Pass | app and SDK sdists/wheels built |
| Clean offline install | Pass with note | succeeds when both app and SDK wheels are supplied |
| CLI consent gate | Pass | missing confirmation exits 2 and creates no database |
| Synthetic demo | Pass | 30 messages → 16 nodes / 22 relationships |
| 5,000-message import | Pass | 5,000 physical / 4,992 unique evidence rows → 603 nodes / 2,325 relationships |
| Initial import performance | Pass for validation scale | 11.56s, 78 MB peak RSS |
| Repeat import | Pass | 0 new records; identical map; 4.93s full rebuild |
| Metadata minimization | Pass | zero body or attachment canaries in 4,992 stored records |
| Database integrity | Pass | `integrity_check=ok`; zero FK violations |
| File permissions | Pass | DB/WAL/SHM mode `0600` |
| Runtime network egress | Pass | import trace showed only an internal Unix `socketpair`; no IPv4/IPv6 connection |
| Path confinement | Pass | `/etc/passwd` preview rejected; vault stayed empty |
| Trusted host | Pass | hostile `Host` returned 400 |
| Browser privacy headers | Pass | CSP/referrer/nosniff; personal API and errors are `no-store` |
| Scope preview | Pass | exact count, address count, size, date range, invalid-date count, retained/excluded fields |
| Consent and progress | Pass | import disabled before consent; queued/import/project/complete states rendered |
| Map rendering and inspectability | Pass with limitations | stable large map, ranked lists, explicit 30/603 object disclosure; user comprehension remains untested |
| Node provenance | Pass | object evidence, total count, observed range, derivation shown |
| Relationship provenance | Pass | typed edges and connection-specific evidence available |
| Evidence minimization | Pass | modal exposed bounded headers only; no canaries |
| Logical reset | Pass | all evidence, cursor, projection, provenance, and job-visible state removed |
| Physical reset | Pass | DB/WAL/SHM scanned; private markers absent; WAL 0 bytes; DB integrity OK |
| Main CI | Pass | GitHub Actions run 29803091406 |

## Findings

### Medium — Source navigation is misleading

“Source” opens the fresh-import onboarding screen. It does not show the current source receipt/status, and there is no explicit “Back to map” action. Reloading or selecting the home link returns to the existing map, so data is safe, but the navigation can feel like a trap.

**Next change:** replace it with a source/status page showing imported path label (or redacted basename), owner identity, message/evidence counts, last cursor, parser version, warnings, re-import, add-source, and back-to-map.

### Medium — Full rebuild is already measurable

A no-op 5,000-message re-import took 4.93 seconds because the projector rebuilds the complete graph. This is intentionally correct and simple, and it remains acceptable for validation. It should become a measured optimization target—not a speculative rewrite—if personal archives exceed the agreed onboarding budget.

**Decision gate:** optimize only if a real archive takes more than 60 seconds to produce the first map or more than 10 seconds to refresh after a no-op import.

### Medium — Product value is untested

Synthetic data verifies mechanics, not recognition. No accessible personal MBOX existed during this sweep. The central hypothesis remains open: whether a deterministic communication map feels more useful than inbox search.

**Next action:** run one bounded personal archive and record usefulness, incorrectness, surprise, privacy comfort, and return intent.

### Low — Equal-weight ranking ties are arbitrary but deterministic

The stress corpus deliberately produced many equal activity counts. “Strongest contact” then resolves alphabetically. This is honest but may feel semantically stronger than the evidence warrants.

**Next change:** label ties (for example, “Top contacts”) or use a transparent secondary recency score before adding any learned ranking.

### Low — Offline wheel install needs the release set

The application wheel depends on the SDK wheel. A fully offline install must supply both artifacts together. The normal workspace path is unaffected.

**Docs change:** show both wheels in offline installation examples.

## UX observations

- The onboarding page is visually polished, restrained, and unusually clear about retained/excluded data.
- The large map remains stable, but labels are necessarily small; ranked lists are the useful primary navigation at 600+ objects.
- The “What stands out” strip gives the map an immediate reading without pretending to infer life meaning.
- Relationship details and evidence are the strongest trust feature in the build.
- The product currently maps communication structure, not “your life.” Keep the claim narrow until more sources and user corrections earn broader language.

## Personal-data validation protocol

1. Export a bounded Gmail or mail-client period as MBOX; start with 6–24 months rather than “all mail.”
2. Place it somewhere readable by the local daemon, such as an explicitly allowed directory under `$HOME`; do not commit or paste private source paths into public artifacts.
3. Confirm the host storage posture. The SQLite vault is not application-level encrypted.
4. Run preview first and sanity-check message count, dates, and invalid-date count.
5. Import, then inspect:
   - top 10 people;
   - top 5 organizations;
   - top 10 threads;
   - three surprising relationships;
   - three obviously wrong or noisy results.
6. Open evidence for at least one node and one relationship.
7. Record the validation questions below.
8. Execute erase/reset and verify the app returns to onboarding.

### Questions to record

Score 1–5 and add one sentence each:

1. **Recognition:** Does the map resemble the selected period?
2. **Novelty:** Did it reveal anything not obvious from memory or inbox search?
3. **Trust:** Could you understand why the displayed objects and relationships existed?
4. **Noise:** How much was mailing-list, notification, or automated-email clutter?
5. **Privacy/value:** Was metadata-only retention proportionate to the value?
6. **Friction:** Was obtaining and selecting MBOX acceptable?
7. **Return intent:** Would you revisit this if it stayed current automatically?
8. **Correction need:** What was the first thing you wanted to merge, hide, rename, or exclude?

## Go/no-go criteria for the next phase

Proceed beyond MBOX validation only if:

- the first personal map is recognizable;
- at least one non-obvious useful pattern appears;
- evidence drill-down creates trust rather than confusion;
- the user would return if updates were automatic; and
- noise can plausibly be fixed with deterministic filters and correction controls.

Do **not** prioritize Gmail OAuth, embeddings, or an LLM if the static map itself is not useful.
