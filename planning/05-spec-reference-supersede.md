# Spec: superseding evidence references (DRAFT, not approved)

## The requirement (user, 2026-11-27)

- "if you look at or reference a superseded citation, the system should be automatically feeding you the newer information"
- "Reads of superseded references obviously must return the superseding information as well as a note that it was superceded, when a reference is superceded, a sweep of nodes using the old one and reviewing should probably be done, with a simple collection of discrepancies escalated to the user for review/correction" (reads: built, build log #56)
- "I guess we need a system to check if a new reference supercedes any old. Perhaps ai agents should be searching stored references first?"
- "Why would a url reload auto supersede? What if it loads an error page? Has a mistake? No longer shows the relevant info?" -> nothing supersedes automatically.
- Who confirms: for document references, "Planner, you can override" (the planner may confirm; it still shows on the user's list). User-quote supersedes: the user only.

## Recorded decisions this builds on

- Escalations are "requirement request" tasks: ordinary task nodes inserted as a sibling before the task they block (`05-module-specs.md` #3, `process-levels.md`). Answered by the parent session or the user.
- One generic node type; queues are views by state (`CLAUDE.md`).
- Reviews are records about one content item, run by clients in review mode (`05-spec-citation-enforcement-and-review.md`; build log #49-#51, #55).
- "Evidence" = user_exchange, proposal_response, document, knowledge_base. Node content items are also stored as references (origin `node`) and are superseded on edit; that is NOT what this spec is about.

## Plain statement

1. **Search first.** Agents search the project's stored references before loading a source or asking the user. Every load or capture response also lists stored references from the same source (URL or file name) and the top same-topic matches (Postgres full-text search), so the agent sees older evidence even if it didn't search.
2. **Candidates, never automatic.** A new evidence reference becomes a *supersede candidate* for an old one when:
   - it comes from the same source (same URL or file name) with different content, or
   - the agent or user proposes it (`planning references propose-supersede OLD NEW`), e.g. a user correcting an earlier statement or newer docs for the same library.
3. **Trial review.** For a candidate, every content item citing the old reference is reviewed against the new copy: each cited range is mapped into it (difflib, built) and reviewed with the normal reviewer. Nothing changes yet. Result: the list of claims that would no longer hold, and whether the new copy looks like an error or a placeholder page.
4. **Confirm.** The candidate plus its trial results go into a **requirement request** task (one per candidate) inserted before the earliest affected task. Content items: old quote, new quote, each affected node and claim with the reviewer's reason.
   - Document reference: the planner may confirm or reject; it stays visible to the user, who can override.
   - User quote: only the user confirms.
5. **On confirm:** the old reference is marked superseded by the new one (reads then follow it, built). Each affected claim's review is reopened against the new version; failures stay on the requirement request as the discrepancy list for correction. On reject: the pair is kept as "not a supersede", with the reason.

## Module list (nested; DRAFT)

- `references/` (existing)
  - `line_range_mapping` (built): old range -> range in the new version.
  - `related_reference_finder` (new, small): same-source and full-text same-topic lookup within a project.
  - `supersede_candidates` (new): candidate records (old, new, origin, status proposed / trial_reviewed / confirmed / rejected, confirmed_by, reason); `confirm` calls the existing `supersede`.
- `content_review/` (existing): add a "trial" review against a named newer reference (same records, flagged trial, never blocks done); reopen reviews of items citing a superseded reference.
- `project_tree/` (existing): `citing_nodes` (built) finds affected items; requirement request creation uses the existing insert-before.
- Commands/routes: propose, list candidates, confirm, reject (permission rules above). CLI entries in the declarative table.
- Guidance: planner + worker rule "search stored references before loading or asking".

## Open points for the user

1. Is a trial review against the new copy the right gate, or should the requirement request be raised for every candidate before any review runs?
2. The model check for "same point" between two user statements (to find candidates without anyone proposing them): include now, or only explicit proposals plus same-source at first?
3. Does a superseded user quote stay citable as history (e.g. "the user first said X, then Y")? Today the citation gate rejects superseded citations.
