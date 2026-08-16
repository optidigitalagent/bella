# SEO change log

## 2026-08-14 — PR 0B public-safe operations bootstrap

- Affected surface: 53 public-safe `.seo/` operational records only.
- Change: PR [#7](https://github.com/optidigitalagent/bella/pull/7) initialized the governed SEO workspace in commit `2fc31ad014c633a0fb396e34f52ced445948b6b0`; merge commit `119a62cfd31a1e5b2b2eab1b3bc07586002bf3a3` was created at 2026-08-14T07:23:41Z.
- Reason: establish one schema-preserving operational source of truth before technical SEO implementation.
- Validation/decision: public-safety and format checks passed; no `.seo/` file was added to the Pages artifact.

## 2026-08-15 — PR 1 technical foundation merged

- Affected surface: `index.html`, `price.html`, `pages-public-manifest.txt`, `robots.txt`, `sitemap.xml`, and `tests/test_pages_artifact_isolation.py`.
- Change: PR [#8](https://github.com/optidigitalagent/bella/pull/8), head `955f9f193ce5266054e5627ad1179189375b8b95`, merged at 2026-08-15T06:34:30Z as `1195107fabf3525d48cf11515bdc0ffb8a0f183d`.
- Reason: establish canonical, robots, sitemap, and fail-closed Pages isolation contracts.
- Validation/decision: unit, exact-artifact, five-viewport rendered, and merge/tree parity evidence passed; no backend/API integration was changed.

## 2026-08-15 — Exact PR 1 production deployment

- Affected surface: the existing 56-file public Pages artifact.
- Change: workflow run [31891801908](https://github.com/optidigitalagent/bella/actions/runs/31891801908) deployed artifact `9248733312` through Pages deployment `5921688840` at SHA `1195107fabf3525d48cf11515bdc0ffb8a0f183d`.
- Reason: release the already reviewed PR 1 technical foundation.
- Validation/decision: build and deploy jobs succeeded; exact artifact/Git parity, public routes, canonicals, robots/sitemap, remote propagation, and private-path isolation were accepted. No rollback, rerun, or second dispatch occurred.

## 2026-08-16 — PR 1 operational closeout branch work

- Affected surface: the 14 authorized `.seo/` operational records on `chore/bella-seo-pr1-closeout`.
- Change: reconcile stale records with the verified merged and deployed PR 1 state.
- Reason: prevent later agents from relying on pre-deploy SHAs, empty release state, or stale authorization.
- Expected effect: a current public-safe handoff, backlog, baseline, QA record, and release closure without changing production bytes.
- Risk: low operational-record risk; entity/NAP/medical facts remain unverified and are not promoted.
- Validation: 53-file parse/schema/safety checks and unchanged 56-file publishing-isolation checks are required before the single commit.
- Release reference: Draft PR number intentionally unassigned until GitHub creates it; this branch is not merged or deployed.
- Decision: stop after opening and verifying one Draft PR. Ready, merge, deploy, sitemap submission, indexing, and external action remain separately authorized scopes.
