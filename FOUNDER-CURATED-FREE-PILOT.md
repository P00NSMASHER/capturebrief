# CaptureBrief founder-curated first-check pilot: scoped path, not a source bypass

**Scope:** at most ten independently identity-reviewed businesses, one free assumption about one publicly accessible federal IT/cyber/cloud pursuit each. This is the equivalent of PermitPlate's supervised founder-curated launch lane, **not** its scored/automated product, and not a claim that any buyer has received a valid check. There is no card, payment, automatic conversion, or free change watch.

## The important separation

- **Scope inquiry:** a buyer may *prepare* a no-send local email request; the operator must independently verify actual email receipt, company identity, the one-per-business limit, eligibility, and possible delivery timing. This step does not require a full multi-decade SAM.gov source index.
- **Case research:** the operator may investigate one specifically selected pursuit against verified first-party SAM.gov sources. The existing `SAM_HISTORY` human-supervised history route is available; its complete-action claim requires independently retained factual review, **not** an automatically generated self-attestation. If the exact family/action history cannot be established, stop or use the full-catalog route. A partial FY2027 archive is not complete history.
- **Current-action proof:** fetch a fresh approved SAM Opportunities API v2 observation for that **exact pursuit** and bind all applicable action and current-resource evidence to it. The successful public API key/health probe for some other solicitation proves only access.
- **Documents/rules:** independently verify all decision-relevant public original attachments, deletion-inclusive manifests, references, exact quoted text, amendments, rule edition/applicability and any unresolved source limitations. Do not say "no amendments," "latest deadline," "all changes," or "bid cleared" without corresponding complete source authority.
- **Private storage:** maintain source originals, intake cases, registry, provider receipts and reviews under approved private encrypted storage with a separately controlled encrypted off-device backup and a tested independent restore. **Cloudflare R2 is one option, not a mandatory dependency.** GitHub Pages, public repository objects, Actions logs and browser local storage are not private customer storage.
- **Deliverable:** do not produce or release the free-check result until the original reservation is valid and `inspect_free_check`, `evaluate_delivery_readiness`, exact Decision Evidence integrity and the original report receipt pass for real non-synthetic observations. Genuine human conclusions and per-message external-send approval remain mandatory. If a provider cannot prove receipt/delivery, never claim delivery.

### Read-only comparison command

```sh
# Current full-catalog admission: expected BLOCKED until fiscal-year catalog/index repair.
python scripts/pilot_preflight.py --stage admission --offer free

# NEW founder-curated intake preparation: explicitly REVIEW REQUIRED, never delivery-ready.
python scripts/pilot_preflight.py --stage admission --offer free --launch-mode founder_curated
```

Both commands intentionally return a non-green exit code when there is no confirmed real-customer readiness. The founder-curated output preserves the stale catalog and absent index as **diagnostics**, and lists per-case official history, live current action and independent private recovery as **post-inquiry obligations**. It does not change any catalog constant, source trust policy, payment integration, report builder, free-check business registry, source release check, review or send authorizer.

## Demonstrated real federal original and review draft

A main-only October 28 test proved the real 35-page original for Treasury RFQ 2031JW27Q00011 (SHA-256 557bceeec58e625376d43678260075d1f96a831afe295035941addf77ae214e4) and independently restored four authentic encrypted public/fictional evidence files on a separate runner. That same original contains a material November 5 vs November 9 response-date contradiction (pages 3 vs 1), along with 60 vs 90 calendar-day price-hold wording (pages 27 vs 33). scripts/prepare_founder_review_packet.py creates a **private, source-limited internal HOLD draft** and remains categorically separate from the existing customer-delivery-ready free-check renderer. It never manufactures complete history, buyer approval, recovery-key custody, charge or email authority. All per-customer release requirements still apply.

## Release boundaries

The launch readiness equivalence to PermitPlate is **ready to prepare and scope customer inquiries**, not evidence that CaptureBrief can already deliver a $149 complete-pursuit review. Do not turn on paid checkout or advertise automatic fulfillment from this status. The full-catalog and paid lanes retain their original proof requirements. The actual Cloudflare-hosted public free-check inquiry is deployed from gh-pages and its content-integrity and no-send tests have passed Chromium and WebKit. PR #90 was superseded and closed; the production site change is PR #94 and production gate repairs #95-#100. The 2026-10-28 first-party Treasury PDF and clean-runner encrypted source proof are documented in CAPTUREBRIEF_FOUNDER_PILOT_SOURCE_PROOF_2026-10-28.md. An inquiry is still not customer acceptance or deliverable authorization.

Before accepting an actual free engagement, the operator must document a feasible source-specific plan, independent receipt of the request, one business identity, private retained storage/recovery, and manual review capacity. Start only after these checks. Any failed per-case audit remains blocked rather than upgrading a candidate into a customer report.


## Implemented on-demand private evidence path (candidate)

The per-pursuit engine uses the existing bounded SAM.gov Opportunities API
client. It collects one solicitation's current record and optionally retains only
the documents needed for that case. It **does not** fetch all archive years,
purchase Cloudflare R2, use the PermitPlate customer database, or replace the
public paid-product source policy. This runs on a protected operator device or
private worker, never on a public website or a job exposing customer data.

First independently import a real received free-check request (see
FREE-CHECK-PILOT.md) to a private case JSON. Use an **encrypted private
filesystem** with suitable access restrictions. On Linux/macOS create an owner-
only workspace with mkdir -m 700; on Windows use operator-only access and
device encryption. Keep paths OUTSIDE Git, Pages, shared sync or CI artifacts.

~~~sh
# Existing private 0700 workspace. Not a Git checkout.
export CB_PRIVATE_ROOT=/secure/private/capturebrief-scoped

# SAM_API_KEY must be set through private secret management;
# never put the key in chat, code, logs, or a CLI argument.
python scripts/prepare_scoped_sam.py observe \
  --case /secure/intake/request-SHA.case.json \
  --private-dir "$CB_PRIVATE_ROOT" \
  --solicitation "EXACT-SOLICITATION-NUMBER" \
  --posted-from 10/01/2026 --posted-to 10/27/2026
~~~

The one-year maximum query window, exact solicitation match, pagination-
complete API response, positive ACTIVE status, approved redirect host, 2 MiB
response bound, five-minute observation freshness and canonical official
buyer URL are checked. Inactive or ambiguous records fail closed. The retained
file sam-current-SHA.json is source-specific and omits the key, raw provider
response body and contact fields. It does not claim complete history.

~~~sh
# Optional: retain ONE operator-retrieved public original, at most 50 MiB.
# A .gov URL is NOT independent evidence of the original file's provenance.
python scripts/prepare_scoped_sam.py retain \
  --case /secure/intake/request-SHA.case.json \
  --private-dir "$CB_PRIVATE_ROOT" \
  --file /secure/incoming/original-public-document.pdf \
  --source-url "https://sam.gov/opp/EXACT-NOTICE-ID/view"

python scripts/prepare_scoped_sam.py verify \
  --case /secure/intake/request-SHA.case.json \
  --private-dir "$CB_PRIVATE_ROOT" \
  --capture "$CB_PRIVATE_ROOT/case-CASE_TAG/sam-current-SHA.json"

# Only AFTER independently completing first-party SAM_HISTORY review and
# enriching the PRIVATE case with that independently retained source evidence:
python scripts/prepare_scoped_sam.py bind \
  --case /secure/reviews/reviewed-case.json \
  --private-dir "$CB_PRIVATE_ROOT" \
  --capture "$CB_PRIVATE_ROOT/case-CASE_TAG/sam-current-SHA.json"
~~~

Before binding, the separately retained first-party SAM_HISTORY receipt MUST
include a manual_review object with exactly: scope=COMPLETE_ACTION_SET,
source_sha256 (the digest of a retained public-source-SHA.bin original),
reviewer_id, reviewed_at (timezone-aware), and review_reference. The retained
source receipt URL must match the history receipt URL. The source bytes are
re-hashed, review age is limited to seven days, and the buyer and current
notice IDs must belong to the same independently reviewed action family.
No software-generated reviewer identity or hash proves that the actual
SAM.gov listing was complete: independent human source verification remains
an explicit release obligation.

Binding calls the existing history/current-authority validators and requires
the original buyer notice and current action in a separately reviewed same-
family action set. Its immutable case-current-SHA.json remains private.
It does NOT mark the buyer assumption supported or complete amendment,
attachment-manifest, reference, rule, Decision Evidence or send gates.

### R2-free encrypted backup and restore

An optional pinned cryptography==46.0.4 dependency provides AES-256-GCM
with scrypt password derivation. The utility protects the original private
request and ONLY recognized, hash-verified scoped evidence, rejecting corrupted
content-addressed receipts, unknown files and unsafe/oversized data. It
does NOT back up a separate registry, other cases, or a production database.
Protect those assets separately.

~~~sh
python -m pip install --only-binary=:all: cryptography==46.0.4

python scripts/scoped_private_backup.py create \
  --case /secure/intake/request-SHA.case.json \
  --private-dir "$CB_PRIVATE_ROOT" \
  --backup-file /secure/backup-staging/scoped-CASE_TAG.cbak

python scripts/scoped_private_backup.py verify \
  --backup-file /secure/backup-staging/scoped-CASE_TAG.cbak

# Copy ONLY the encrypted .cbak to separately access-controlled OFF-DEVICE
# storage using an independently approved transport. Download a fresh copy
# to another authorized machine and then restore into a new private location:
python scripts/scoped_private_backup.py restore \
  --backup-file /secure/from-remote/scoped-CASE_TAG.cbak \
  --output-dir /secure/new-empty-restore-path
~~~

The CLI requests an independently retained recovery phrase interactively;
never paste it in chat, email or commits. A local restore proves only local
authenticated-byte recovery. The free-check reservation registry is **not included** in the per-case `.cbak`. Back up and independently restore that registry using `FREE-CHECK-REGISTRY-RECOVERY.md`; a stale restored snapshot must not reset admission limits.

An encrypted backup must be independently
copied OFF DEVICE, fetched again, and restored under independent key control
before accepting real engagements. A separate private GitHub repository can
hold **encrypted backups only** if later provisioned and permission-scoped;
never upload decrypted customer data to any public repository or unapproved
third-party workspace.

### Boundaries still in force

- Implemented: on-demand API query, private immutable current-source evidence,
  exact-intake identity binding, optional document retention, manual-history
  binding, local AES-GCM backup, source/restore integrity QA on Linux/Windows.
- Not proven: a real customer case fully delivered, live human history and
  manifest review, publisher authentication merely from a file hash,
  protected production host and tested OFF-DEVICE recovery, or customer
  consent to receive messages.
- Existing inspect_free_check, evaluate_delivery_readiness, human Decision
  Evidence and per-message approval remain mandatory. Neither a successful
  SAM observation nor a checksum can authorize a delivered customer report.
