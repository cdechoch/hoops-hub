#!/bin/bash
# Run on your Mac. Downloads the HoopsMatic sheets from your own connection (GitHub's servers can be blocked),
# saves them under config/hoopsmatic/, then commits and pushes so the next update uses them.
set -e
cd "$(dirname "$0")/.."
mkdir -p config/hoopsmatic
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
ok=0
for f in contracts rm-roster rm-exceptions draft-csv rm-holds awards; do
  if curl -fsSL -A "$UA" -H "Accept: text/csv,*/*" "https://hoopsmatic.com/api/$f" -o "config/hoopsmatic/$f.csv.tmp" && head -c 400 "config/hoopsmatic/$f.csv.tmp" | grep -q ","; then
    mv "config/hoopsmatic/$f.csv.tmp" "config/hoopsmatic/$f.csv"; echo "saved $f ($(wc -l < config/hoopsmatic/$f.csv) lines)"; ok=$((ok+1))
  else
    rm -f "config/hoopsmatic/$f.csv.tmp"; echo "could not download $f"
  fi
done
if [ "$ok" -eq 0 ]; then echo "Nothing downloaded. Open hoopsmatic.com/contracts in your browser first, then tell Claude what you see."; exit 1; fi
git add config/hoopsmatic
git commit -m "Update HoopsMatic sheets" || echo "no changes"
git push
