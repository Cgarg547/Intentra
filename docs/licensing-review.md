# Apache-2.0 adoption and third-party licensing review

Review date: 2026-11-05 UTC. Owner-approved INTENTRA license: **Apache-2.0**.
Copyright notice for INTENTRA's original work: **Copyright 2026 Chirag Garg**.

## Scope and conclusion

The root LICENSE was downloaded from the
[official Apache text](https://www.apache.org/licenses/LICENSE-2.0.txt), without
editing its wording, whitespace, appendix or placeholders. SHA-256:
`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.
The original-work copyright statement lives in README and NOTICE, not inside the
canonical license text. Existing third-party notices were not changed.

No obvious barrier was found to licensing INTENTRA's original source under
Apache-2.0 while retaining the reviewed dependencies under their own terms.
This does **not** certify every possible binary distribution or relicense vendor
code, data, fonts, logos, hosted APIs or model weights. Release packaging still
needs the distribution-specific notice/source checks listed below.

Inspected evidence:

- All 474 non-root entries and declared license expressions in
  `apps/web/package-lock.json`, including optional platform packages.
- Installed license files for the main JavaScript packages and flagged native,
  data and copyleft components; 131 license/notice files enumerated under
  `next/dist/compiled`, with textual scans for additional licensing families.
- Installed Python distribution metadata and license-file presence, compared
  with API runtime/development requirements. The installed environment is not a
  frozen transitive Python lock or a complete release SBOM.
- Tracked application imports, source/license headers, public asset inventory,
  favicon, and asset references. No application references to the five retained
  public SVG templates were found; public-folder assets can still be served or
  redistributed even when not referenced.
- The project contains dependency imports, not a tracked `node_modules` or `.venv`
  vendor tree. Absence of a copied-code header is not proof of provenance.

## Direct JavaScript dependencies

| Package | Observed version | Upstream license evidence | Treatment |
| --- | --- | --- | --- |
| Next.js | 16.4.3 | MIT, installed `next/license.md` | Preserve MIT and bundled component notices in redistributions |
| React / React DOM | 19.3.0 | MIT, installed LICENSE files | Preserve upstream notices |
| next-themes | 0.4.6 | MIT, installed license.md | Preserve upstream notice |
| lucide-react | 1.66.0 | ISC, plus MIT for listed Feather-derived icons in its LICENSE | Preserve both notice sets; do not replace their authorship with INTENTRA's copyright |
| Recharts | 3.10.1 | MIT, installed LICENSE | Preserve upstream notice |
| Playwright test tooling | 1.64.1 | Apache-2.0 plus NOTICE | Keep upstream NOTICE if distributing that tooling |
| TypeScript | 5.9.3 | Apache-2.0 | Keep upstream license; project adoption does not rewrite it |

The full lockfile license counts were: MIT 365; ISC 29; Apache-2.0 37;
BSD-2-Clause 7; BSD-3-Clause 3; MPL-2.0 13; LGPL-3.0-or-later 10;
Apache-2.0 AND LGPL-3.0-or-later 3; Apache-2.0 AND LGPL-3.0-or-later AND MIT 1;
MIT AND ISC AND BSD-3-Clause 1; and one each of 0BSD, BlueOak-1.0.0, CC-BY-4.0,
CC0-1.0 and Python-2.0. These are metadata declarations, not a legal conclusion
that all packages are Apache licensed or all platform variants are installed.

## Components requiring release-specific attention

| Component | Evidence | Outstanding action / compatibility boundary |
| --- | --- | --- |
| sharp + prebuilt libvips | sharp 0.35.5 is Apache-2.0; optional `@img/sharp-libvips-*` 1.3.4 declare LGPL-3.0-or-later; installed Darwin ARM64 README lists additional native-library licenses | Before shipping a standalone server/container/native bundle, preserve component notices and verify applicable source/relinking obligations for the actual binaries. Do not describe the complete image stack as solely Apache-2.0 |
| MPL files | `lightningcss` 1.32.0 and platform packages, dev `axe-core` 4.14.0, Python `certifi` 2026.10.23, Next's bundled `@vercel/og` notices | Keep their licenses and applicable covered-source availability/modification notices. Separate original application files need not be relabeled MPL merely because the dependency is present; verify actual packaging |
| Attribution data | `caniuse-lite` 1.0.30001820, CC-BY-4.0; Next compiled `glob/LICENSE` includes an attribution-licensed component notice | Retain attribution/license and any change indication for redistributed covered data. Build output and source distribution must be assessed separately |
| Native image library subcomponents | Installed libvips README includes BSD, LGPL, MIT, zlib/IJG and patent-license references | The package's top-level SPDX identifier is not a substitute for its complete notice inventory |
| Bundled Next components | 131 license/notice files found; `@vercel/og/LICENSE` and its satori license include MPL references | Keep bundled notices rather than assuming Next's MIT label covers every constituent |

Primary references: [sharp licensing](https://sharp.pixelplumbing.com/install/#licensing),
[Mozilla's MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/),
[LGPL 3.0](https://www.gnu.org/licenses/lgpl-3.0.html), and
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).
The installed component license text remains the operative distribution evidence.
No dependencies or binaries were modified, statically relinked, vendored or removed
as part of this license change.

## Python dependencies

Direct requirements include FastAPI, SQLAlchemy, Alembic, Pydantic, pwdlib and
argon2-cffi (MIT); uvicorn and HTTPX (BSD-3-Clause); asyncpg and pytest-asyncio
(Apache-2.0); pytest (MIT); and email-validator (Unlicense). Installed transitives
include permissive BSD/ISC/MIT/PSF licenses, dual Apache/BSD packaging, and the MPL
certifi package identified above. Installed metadata/license files were reviewed;
all installed distributions exposed at least one license file in metadata.

Retain Python dependency license files when distributing an environment or image.
A requirements file normally references external packages; it does not convert
them into INTENTRA-owned Apache source. The local Python interpreter and platform
runtime also have their own terms.

## Assets, branding, fonts and model artifacts

- `apps/web/public/{next,vercel,file,globe,window}.svg` and
  `apps/web/src/app/favicon.ico` are retained scaffold/template-era assets.
  Repository history ties these files to the initial scaffold, but the repository
  does not contain a separate asset-rights attestation. Next/Vercel marks are not
  INTENTRA marks. Verify provenance and applicable trademark permissions, or
  replace/remove unused template branding in a separately scoped UI change.
  No assets were removed or relabeled in this pass.
- Current root layout no longer imports Google-hosted Geist fonts; no tracked
  `.woff`, `.woff2`, `.ttf` or `.otf` files were found in app source/public assets.
  Any font retained in generated build artifacts needs its own notices when
  distributed. Generated output was not relicensed or cleared by this review.
- Lucide/Feather icon code remains under its original notices. INTENTRA branding
  uses existing application markup/icons; no Ramp assets or source were added
  by this workstream. Ownership of other contributions is still an owner matter.
- Ollama is a separately installed runtime, not bundled project source. Its
  [runtime license](https://github.com/ollama/ollama/blob/main/LICENSE) is MIT;
  [upstream Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B) declares Apache-2.0.
  Confirm the exact local model artifact's provenance/license before redistributing
  weights; this pass did not contact Ollama, inspect weights, or download models.
- PayPal and optional sponsor APIs remain subject to their service/trademark terms.
  No new SDK, commercial grid, sponsor service, stock image, music or media was
  added. A future library or demo video needs its own review.

## Checks and remaining release gates

1. Root LICENSE is byte-identical to the 11,358-byte official download; the
   standard appendix remains unmodified.
2. README identifies Apache-2.0 and Copyright 2026 Chirag Garg; NOTICE records
   original-work scope and preserves the separation from third-party rights.
3. Git checks passed: `git ls-files --error-unmatch LICENSE` succeeds,
   `git check-ignore --no-index LICENSE` returns 1 (not ignored), and the staged
   bytes match the official text. Only LICENSE is staged, satisfying the owner's
   explicit tracking requirement; no other work is staged by this pass.
4. GitHub recognition remains unverified until an approved commit/push followed
   by anonymous public verification. No public license detection is claimed here.
5. Before publishing binaries/containers or removing upstream files, produce a
   distribution-specific inventory/notices bundle and address LGPL/MPL/CC-BY
   obligations plus template branding provenance. This review is not a replacement
   for that release-artifact inspection.
