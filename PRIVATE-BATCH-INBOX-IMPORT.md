# CaptureBrief private batch inbox importer — draft candidate

**Status: operator-only candidate, no public deployment or customer release.**

This workflow makes the existing strict buyer-draft-to-case importer usable for a
folder of saved customer requests. It does **not** read Gmail or Outlook, open
mailboxes, automatically approve payments, fetch SAM.gov sources, contact buyers,
or start work. It accepts saved, locally reviewed CaptureBrief text drafts only.

## One-time private folder setup

Create **two existing, separate private folders** outside the public GitHub
checkout, Pages publishing directory and cloud-synced source-control trees:

- `incoming`: operator-selected CaptureBrief `.txt` request drafts.
- `cases`: imported case JSON files and immutable import receipts.

For example, on an authorized Windows PC, create
`%LOCALAPPDATA%\CaptureBrief\private-inbox` and
`%LOCALAPPDATA%\CaptureBrief\private-cases` (prefer a host-encrypted
volume and tightly scoped local permissions). Do not move or copy actual
buyer drafts into the public Git repository, Actions, or this conversation.

From the source checkout with the proposed PR applied, run:

```powershell
py -3 scripts/batch_import_request_drafts.py --input-dir "$env:LOCALAPPDATA\CaptureBrief\private-inbox" --output-dir "$env:LOCALAPPDATA\CaptureBrief\private-cases"
```

The command reads **only immediate `.txt` files**, never recursively. It refuses
linked directories, symbolic-link drafts, missing output roots and roots nested
inside one another. It validates at most **100** requests per invocation by
default; `--max-files N` can reduce that cap, not increase it above 100.
If the input contains more candidates than permitted, it fails *before*
creating any case or receipt. Non-text files are ignored and counted.

## Preview before importing

Before creating case files, inspect the **read-only preview**:

```powershell
py -3 scripts/batch_import_request_drafts.py --preview --input-dir "$env:LOCALAPPDATA\CaptureBrief\private-inbox" --output-dir "$env:LOCALAPPDATA\CaptureBrief\private-cases"
```

The preview parses and validates every eligible saved draft against the
same existing buyer-intake contract, identifies exact duplicates and counts
requests needing attention. It **does not create, repair, delete, or overwrite
any case, receipt, lock, or source draft**. Its states are:

- `NEW_VALIDATED`: syntactically valid input with no existing named output.
- `EXISTING_UNVERIFIED`: both destination files exist; the preview has **not**
  verified their contents, customer identity, or payment.
- `PARTIAL_UNVERIFIED`: one destination artifact exists; a subsequent actual
  import might be able to recover it, but preview never attempts recovery.
- `DUPLICATE`: an identical saved request was already observed earlier in
  this preview invocation; it is not an additional unique request.
- `BLOCKED`: invalid, linked, oversized, or otherwise unreadable input.

Preview results use `BATCH_PREVIEW_READY_FOR_REVIEW`,
`BATCH_PREVIEW_PARTIAL_REVIEW_REQUIRED`, or `BATCH_PREVIEW_NO_REQUESTS`.
They carry `preview_only=true`, all actual-import counters set to zero,
and separate counters `preview_new`, `preview_existing_unverified` and
`preview_partial_unverified`. Partial previews exit with code 3, as actual
imports do, so an operator cannot mistake rejected requests for acceptance.
The preview validates only **local input syntax and path existence**; it
does not establish payment, source authenticity, delivery, recovery, or
that a future import will succeed if a file changes.

After reviewing preview results, run the regular command **without**
`--preview` to attempt publication with the existing per-file locking,
fingerprint consistency and complete on-disk integrity validation.

## Expected output

The utility writes a private pair per **distinct exact input byte sequence**:

- `request-<full-request-SHA256>.case.json`
- `request-<full-request-SHA256>.receipt.json`

That content address automatically suppresses *exact copies*, including
same-message files with different names. A retry after interruption preserves
the original case timestamp and completes only the missing matching artifact.
A changed buyer request never silently overwrites an earlier case.

The stdout JSON reports counts for `created`, `reused`, `recovered`,
`duplicates`, `blocked`, and `ignored_non_txt`, with only hashed filename
tags and generic failure types for individual results. **No buyer names, work
emails, private paths or request text are printed.** The hashed filename tags
can be matched locally if an operator needs to investigate a blocked file.

An empty inbox (or a folder containing no `.txt` drafts) reports
`BATCH_NO_REQUESTS` so it is not mistaken for admitted customer work.

The exit code is **0** when there are no requests or when every eligible draft
was accepted/reused or safely deduplicated; **3** when some drafts were blocked
(valid drafts may still have been imported); **2** for an invalid batch configuration. A blocked input is
never categorized as an accepted case. If a source changes between the batch
fingerprint and the single-request importer's second read, the batch refuses
publication under an incorrect request digest.

## Deliberate limitations

This is exact-*byte* duplicate prevention within the selected private output
folder, **not semantic duplicate detection**. Minor edits, line-ending changes,
or forwarding the same message as a differently formatted body can produce a
different case and require operator reconciliation. It does not prove receipt
of an email, customer identity, successful $149 Stripe payment, publisher
source completeness, eligibility, delivery readiness, or any 14-day watch.

Each case's assumptions remain **UNPROVEN**; the existing import receipt
retains `purchase_claim_verified=false`, and the batch report always marks
`payment_verified=false`, `external_send_authorized=false`, and
`customer_release_authorized=false`. A human operator reviews every admitted
case before action. Do not store real intake in GitHub, CI artifacts, ChatGPT
or public websites.

## Reproducible validation

```powershell
py -3 -m unittest tests.test_batch_request_drafts -v
py -3 -m unittest tests.test_request_draft -v
```

The dedicated Linux/Windows workflow executes these only with **fictional**
buyer drafts and disposable temporary directories. No real customers,
communications, payment API calls, or private source originals are used.
