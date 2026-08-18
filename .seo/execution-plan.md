# SEO execution plan

## Verified scope

- Requested mode: implement a public-safe operational-record closeout.
- Authorized operations: audit, branch, edit, tests, one commit, one normal push, and one Draft PR.
- Excluded operations: Ready for review, merge, deploy, release, sitemap submission, indexing request, and every external action.
- Target repository and branch: `optidigitalagent/bella`, `chore/bella-seo-pr1-closeout`, based directly on `origin/main` at `1195107fabf3525d48cf11515bdc0ffb8a0f183d`.
- Production URL: `https://belladentclinik.kr.ua`.

## Dependency-ordered batches

| Batch | Risk area | Baseline | Change | Acceptance test | Owner | Authorization needed | Status |
|---|---|---|---|---|---|---|---|
| 0A | Publishing isolation | Pages previously published repository content too broadly | Introduce an explicit public manifest and fail-closed artifact verification | Internal paths absent and the exact public inventory builds | Engineering | completed authorization | Completed in PR #6 |
| 0B | Operations governance | No governed `.seo/` workspace | Initialize 53 public-safe operational artifacts | 2 JSON, 13 YAML, 29 CSV, and 9 Markdown files parse and remain private | SEO operations | completed authorization | Completed in PR #7 |
| 1 | Technical foundation | Canonical, robots, and sitemap contract incomplete | Add canonical signals, robots, sitemap, and isolation regression tests | PR #8 tests, exact artifact, render parity, merge/tree parity, and deployment acceptance pass | Engineering | completed authorization | Completed and deployed |
| 1 closeout | Operational state | `.seo/` still describes the pre-PR-1 state | Reconcile exactly 14 public-safe records | Exact 14-file diff; 53-file schema/safety pass; unchanged 56-file Git artifact | SEO operations | audit, branch, edit, tests, commit, push, draft_pr | Current |
| 2A | Entity facts | Published values are not owner-confirmed and conflicts remain | Establish a governed entity facts baseline only | Approved sources, owners, allowed surfaces, and professional-review gates are complete | Client + SEO operations | client confirmation and separate PR | Next after this Draft PR |
| 2B | Entity/home/local | No public entity implementation is safe before facts are ready | Apply only approved entity, home, contact, local, metadata, asset, and Schema changes | Visible fact parity, structured-data validation, NAP consistency, browser QA, and isolation pass | Engineering + reviewers | separate implementation authorization | Later |
| 3+ | Services/content/measurement/performance/external | Evidence, access, or approval remains incomplete | Execute one bounded risk area per later PR or external-action batch | Area-specific acceptance tests and direct authorization pass | Assigned owner | separate authorization per scope | Later |

No public entity implementation or Schema work may begin before fact confirmation. Sitemap submission and indexing requests require separate explicit authorization. Keep one high-risk area per pull request; merge or deployment never follows implicitly from passing tests.

## 2026-08-18 reconciled sequence

- Completed: publishing isolation; `.seo/` bootstrap; technical foundation; entity facts; Entity/Home/Local; PR #11 merge and deployment.
- Current: one `.seo/`-only architecture research PR mapping `/implantatsiia-zubiv.html` as `research_complete__implementation_blocked`.
- Next after this PR: obtain approved implantation offering/scope, approved Ukrainian copy, approved assets and permissions, current price approval if used, CTA confirmation, and a qualified professional reviewer with provenance; then separately authorize and implement exactly one public service page.
- Later gates: exact public tests and browser QA; independently authorize Ready; authorize merge separately; authorize any deployment separately. No deployment is needed for this `.seo/`-only research PR.
- Deferred areas remain safe sheet-fed DOM construction, performance, approved descriptions, measurement, external profiles, sitemap submission, and indexing. None is authorized here.
