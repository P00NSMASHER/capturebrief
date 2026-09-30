#!/usr/bin/env bash
set -euo pipefail

rm -rf dist
mkdir -p dist

public_files=(
  "404.html"
  "_headers"
  "_redirects"
  "data-handling.html"
  "decision-evidence-sample.html"
  "favicon.svg"
  "index.html"
  "privacy.html"
  "robots.txt"
  "sample.html"
  "site.webmanifest"
  "sitemap.xml"
  "terms.html"
  "thanks.html"
)

for file in "${public_files[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required public file: $file" >&2
    exit 1
  fi
  cp "$file" "dist/$file"
done

if [[ ! -d assets ]]; then
  echo "Missing required public assets directory" >&2
  exit 1
fi
cp -R assets dist/assets

# Discovery-only PA x402 front door.
# Keep payment verification/settlement on the existing Floot API; only static
# catalogue files are published here for anonymous crawler reads.
discovery_root="x402/pa-entity"
for file in "$discovery_root/.well-known/x402" "$discovery_root/openapi.json"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required PA x402 discovery file: $file" >&2
    exit 1
  fi
done
mkdir -p dist/.well-known dist/x402/pa-entity/.well-known
cp "$discovery_root/.well-known/x402" dist/.well-known/x402
cp "$discovery_root/openapi.json" dist/openapi.json
cp "$discovery_root/.well-known/x402" dist/x402/pa-entity/.well-known/x402
cp "$discovery_root/openapi.json" dist/x402/pa-entity/openapi.json

# Deployment boundary assertion: internal product/research material must never be copied.
for forbidden in   "capturebrief_core" "tests" "fixtures" ".github"   "PRODUCT-CORE.md" "RULE-SOURCES.md" "RULE-SOURCE-CATALOG.json"   "DECISION-EVIDENCE.md" "OUTCOME-LEDGER.md" "BUSINESS-MODEL-v6.md"   "BUSINESS-MODEL-v7.md" "SOURCE-POLICY.md" "REFERENCE-REVIEW.md"; do
  if [[ -e "dist/$forbidden" ]]; then
    echo "Forbidden internal path entered public deploy: $forbidden" >&2
    exit 1
  fi
done

echo "CaptureBrief public deploy staged in dist/"
