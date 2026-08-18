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

## 2026-08-16 — PR #9 operational closeout merged

- Affected surface: the 14 reviewed `.seo/` closeout records only.
- Change: PR [#9](https://github.com/optidigitalagent/bella/pull/9), head `e3390e5e4bfb8894f2a42c784b3db6b972e5b03b`, merged at 2026-08-16T12:41:41Z as `db7bb03a06e4083a26394cb355b4c3512c689ec3`.
- Validation/decision: `main` is ahead of deployed SHA `1195107fabf3525d48cf11515bdc0ffb8a0f183d` only through operational `.seo/` records; no public deployment is required.

## 2026-08-16 — Direct client entity confirmation received

- Confirmed: current Bella Dent Clinic brand, core NAP, hours, category, Maps location, current social-link state, logo permission, and primary conversion.
- Normalized: the current street is `Федора Караманиць`; `Ватутіна` remains a legacy alias under municipal decision No. 1515.
- Boundary: this confirmation is not qualified medical review, review/case provenance, patient consent, treatment-outcome evidence, or formal trademark/patent registration evidence.

## 2026-08-16 — Entity facts baseline branch work

- Affected surface: exactly the 14 authorized `.seo/` records on `chore/bella-seo-entity-facts`.
- Change: record a public-safe facts baseline and the current/legacy address distinction before any public entity/home/local work.
- Release reference: Draft PR number intentionally unassigned until GitHub creates it; this branch is not merged or deployed.
- Decision: stop after one Draft PR. Ready, merge, public-site/Schema implementation, deploy, indexing, and external-profile actions require separate authorization.

## 2026-08-17 — PR #11 merged and exact-SHA production deployment

- PR #11 merged as `890ed5df7f001f754df5e79eeddcef14d88e5844` with parents `a32867ebb0c7054b86329c15727d535daf12574d` and `071be5817779ffd12d3d13854ccd6e35ed7b9d31`.
- Workflow `32037331811` built artifact `9291103287`; Pages deployment `5946162353` succeeded at the same SHA.
- Production acceptance retained the exact 56-file contract and aggregate `3ee478233e604f88c4fa80edc8394f646ac067a808d42df78479d502a2c6c41d`.

## 2026-08-18 — Priority-service architecture research branch work

- Affected surface: exactly the 24 authorized existing `.seo/` records on `chore/bella-seo-priority-service-architecture`.
- Change: record dated Ukrainian/Russian query observations, first-party and weak-directory evidence, current Bella content depth, and one governed prospective implantation mapping.
- Architecture decision: `/implantatsiia-zubiv.html`, Ukrainian only, `research_complete__implementation_blocked`; no public file, canonical, sitemap entry, Schema, medical copy, or asset was created.
- Release reference: no future PR number is assigned in advance; this branch is not merged or deployed and has no public-byte impact.
- Decision: stop after one Draft PR. Ready, merge, public implementation, deployment, sitemap submission, indexing, external-account actions, and professional approval remain separate.

## 2026-08-18 — PR #12 merge reconciliation and implantation confirmation/copy draft

- PR #12 merged as `3c55b3213be82b2c064c03e6c991ee7d73beb091`; it changed only `.seo/` architecture records and required no deployment. Production remains `890ed5df7f001f754df5e79eeddcef14d88e5844` with the unchanged 56-file public artifact.
- Current branch: `chore/bella-seo-implantation-confirmed-copy-draft`; affected surface: exactly the 20 existing `.seo/` paths in the fresh direct authorization.
- Change: normalize the 2026-08-18 client/owner-side confirmation; select the live public Sheet over the static fallback for current implantation names/prices; record 29/29 amount/currency parity and the exact three name-only fallback drifts; and prepare a source-mapped, non-public Ukrainian draft with clinical placeholders.
- The branch is not merged or deployed. No future PR number is assigned in advance. `prices.js` is not repaired here; its later three-name synchronization is a separate public-byte PR.
- Decision: stop after exactly one Draft PR. Ready, merge, deploy, public implementation, medical approval, reviewer attribution, sitemap/indexing, and external-account actions remain separate and unauthorized.
