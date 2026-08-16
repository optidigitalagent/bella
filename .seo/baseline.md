# SEO baseline

Captured: 2026-08-16T08:15:59Z (2026-08-16T11:15:59+03:00, Europe/Kyiv)

## Evidence-backed deployed state

- Repository: `optidigitalagent/bella`; default branch: `main`.
- `origin/main`: `1195107fabf3525d48cf11515bdc0ffb8a0f183d`.
- Deployed SHA: `1195107fabf3525d48cf11515bdc0ffb8a0f183d`.
- PR 1: [#8](https://github.com/optidigitalagent/bella/pull/8), merged 2026-08-15T06:34:30Z.
- Deployment workflow run: [31891801908](https://github.com/optidigitalagent/bella/actions/runs/31891801908); build job `95029074327` and deploy job `95029100651` succeeded.
- Pages deployment: `5921688840`, successful at the exact deployed SHA. Pages uses the workflow build type, the custom domain remains `belladentclinik.kr.ua`, HTTPS is enforced, and the certificate is approved.
- Exact artifact: ID `9248733312`, 56 files, Git tree `c4cfd74020e782a74c1341613d8072a0a52246d4`, public-payload aggregate `91db82f83e6ec8a550240f0b05f05a5650eeb157771d20fbabd8135ae5fca95a`, manifest SHA-256 `0888f7c65e3e6cb1db0780f0f165c057c56dd5a9e49757d9b465a0b55df2609d`, and GitHub archive digest `sha256:a414343efd0ca991300c584ae2c9c4728f3cfd122fb9cf46363cdb152303562f`.
- Exact Git-object comparison found all 56 downloaded artifact files byte-identical to `origin/main`.

## Crawl, canonical, and isolation contract

- `/`, `/index.html`, `/price.html`, `/robots.txt`, and `/sitemap.xml` returned 200 in bounded local HEAD checks on 2026-08-16.
- `/index.html` remains a 200 response with canonical `https://belladentclinik.kr.ua/`; it is not a server redirect.
- `/price.html` remains a 200 response with canonical `https://belladentclinik.kr.ua/price.html`.
- `robots.txt` allows crawling and names the production sitemap. The sitemap contains exactly the home and price canonical URLs.
- HTTP apex, HTTP `www`, and HTTPS `www` normalize to the HTTPS apex. `/price` returned 200 with the price canonical; `/price/` returned 404.
- `.seo/`, backend, workflow, documentation, script, test, manifest, package, and legacy HTML paths are excluded from the 56-file artifact. Sampled internal and random-missing routes returned 404.
- No JSON-LD or analytics tag was found in the deployed source. PR 1 did not change the separated API, CORS, Railway, form, Clinic Life, or Sheets integration code.

## Acceptance and known limitations

- No P0 finding remains after deployment acceptance.
- Earlier local routing was unreliable; retained Check-Host propagation reports independently showed public-route 200s and private-route 404s across nine responding nodes, while one node timed out. Current bounded local route checks succeeded.
- Retained multi-region evidence showed public API health from two Ukraine nodes and six other valid nodes; this closeout created no new remote measurement.
- Known non-blocking work remains: owner confirmation for entity/NAP and Bella/Nika conflicts; medical, doctor, review, and case provenance; the missing price background image; image performance; safe doctor-sheet DOM handling; measurement; approved metadata/assets; and priority service-page architecture.
- Published website values remain `owner_confirmation_pending`; this baseline does not promote them to verified business facts.

## Next operational stage

Independently verify this Draft PR and separately authorize the Ready-for-review transition. Entity facts require client confirmation and a later facts-baseline PR before any public entity, home, local, or Schema implementation.
