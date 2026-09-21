# CaptureBrief: verify the deliverable, not just the command's exit code

Updated: 2026-09-21. Product engine only; GitHub Pages remains the website target.

## Confirmed defect and scope

At baseline `6b24f4c78aa4c39b924ff9d6babe0ccf5e541cb3`, the bundle CLI called the
ZIP builder successfully and then fell through to its generic text-output
handler. That handler replaced the ZIP at `-o` with the JSON receipt. The
command still exited successfully. Separately, `--overwrite` allowed the case
input and bundle output to point to the same file.

The existing builder tests passed because they exercised the function, not
the final command-produced file. The old workflow invoked the CLI without
opening the resulting ZIP.

Tests-only commit `4d6ec4a73aeb4e4f6c1730ef1e667e06a17373bd`, Product Core run
`35667458798`, reproduced three failing assertions: a new output was not a ZIP,
explicit overwrite still left non-ZIP output, and using the input as output did
not fail. The other 366 tests passed. These were temporary test files, not
customer records. This investigation makes no claim about past customer harm.

## Repaired operator contract

`bundle -o` writes only the archive to that path. Its JSON receipt is printed to
standard output, then the command returns before the generic text writer.
Input/output identity checks reject equal paths, resolved symlinks and existing
hardlink aliases, including with `--overwrite`.

The actual output file is reopened by the verifier and checked against the
builder's independently returned receipt before the CLI reports success.

```bash
# Keep these paths distinct. Do not redirect stdout to the ZIP or case input.
python -m capturebrief_core.trace_cli bundle case.json \
  -o delivery.zip > delivery-receipt.json
```

The receipt contains `artifact_verification`. A mismatch returns a nonzero exit
status; neither building nor verifying authorizes an external message.

## Check an existing delivery later

Use the digest from the original retained receipt, not a digest newly computed
from the file being checked:

```bash
EXPECTED_SHA=$(python -c "import json; print(json.load(open('delivery-receipt.json'))['bundle_sha256'])")
python -m capturebrief_core.trace_cli verify-bundle delivery.zip \
  --expected-sha256 "$EXPECTED_SHA"
```

Optional `--case-id` and `--case-sha256` bind the check to the intended case.
The verifier is read-only and prints JSON to stdout; it has no output-path
option that could replace the archive. Exit 0 means `VERIFIED_INTEGRITY`;
exit 2 means verification failed. Keep the original receipt separately and
under access control. The program cannot authenticate how that receipt was
obtained.

## What is checked

- Exact whole-archive SHA-256 against the caller-supplied reference.
- Exactly the six allowed payloads plus `delivery-manifest.json`; no extra,
  missing, duplicate, directory or symbolic-link members.
- Every payload's size and SHA-256 against the delivery manifest.
- Strict JSON objects, duplicate-key refusal, package schemas and consistent
  case/family identifiers and case fingerprints.
- Matching evaluation timestamps across the package metadata.
- The watch baseline's retained fingerprint and no-automatic-decision flags.
- Explicit no-send flags and the package's privacy declarations.

Input is limited to 32 MiB, each expanded member to 16 MiB and total expanded
content to 64 MiB. The verifier never extracts files, renders HTML, executes
contents, calls an external API or sends a message. Larger packages fail for
operator review rather than silently widening these limits.

## Important limits

Integrity is not correctness or authenticity. A valid hash does not establish
publisher authenticity, current source status, legal applicability, qualified
human approval, or a customer's eligibility. Privacy declarations are checked,
but this is not a classifier proving arbitrary free text contains no sensitive
information. Existing evidence/release checks and human review still apply.

This checks the bytes read at verification time, not a permanent guarantee about
the future contents of a filesystem path. A changed file must be checked again.
The command's path check is not a lock against hostile concurrent filesystem
changes. Keep the working case and delivery directory under operator control.

Previously generated CLI outputs should be verified before use. A JSON receipt
with a `.zip` filename must not be treated as a customer package; rebuild from
the retained intact case using the repaired command. Do not infer a successful
delivery from an older command exit code alone.

## Regression gate

`tests/test_delivery_command.py` invokes the real CLI in separate processes.
`tests/test_delivery_verify.py` starts with actual archives from the real product
builder and applies small controlled changes. These tests do not stub the source
or rule-review engines into returning PASS.

The Product Core workflow now independently opens the command-produced ZIP,
checks CRCs, compares its digest/size to the separately saved receipt, and runs
the read-only verifier. Full regression discovery and existing evidence gates
remain enabled. These tests are software evidence, not a completed live buyer
review, external calibration, payment or delivery.
