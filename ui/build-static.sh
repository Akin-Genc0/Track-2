#!/bin/sh
# Assemble the hosted Fathom site (used by Vercel, see vercel.json).
# Only the page itself and the system's decisions (output/dev.jsonl) are published.
# The participant dataset is never published: visitors drop the organisers' workbook
# into the page and it is processed inside their browser.
set -eu
out="${1:-_site}"
here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
rm -rf "$out"
mkdir -p "$out/data"
cp "$here/index.html" "$here/styles.css" "$here/app.js" "$here/loader.js" "$here/countries.json" "$out/"
if [ -f "$root/output/dev.jsonl" ]; then cp "$root/output/dev.jsonl" "$out/data/dev.jsonl"; fi
bad=$(find "$out" \( -iname '*.xlsx' -o -name 'bundle.json' -o -name 'customers.jsonl' -o -name 'hits.jsonl' \
  -o -name 'alerts.jsonl' -o -name 'notes.jsonl' -o -name 'kyc_checks.jsonl' -o -name 'accounts.jsonl' \) -print)
if [ -n "$bad" ]; then echo "Dataset files found in the site, refusing to deploy:"; echo "$bad"; exit 1; fi
ls -la "$out" "$out/data"
