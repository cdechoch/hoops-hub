#!/bin/bash
# Run on your Mac right after copying the "NBA Future Draft Picks By Team" page. Checks the clipboard before saving it.
set -e
cd "$(dirname "$0")/.."
pbpaste > /tmp/team_picks_check.txt
n=$(grep -c "Future NBA Draft Picks" /tmp/team_picks_check.txt || true)
lines=$(wc -l < /tmp/team_picks_check.txt)
if [ "$n" -lt 30 ]; then echo "Clipboard has $n teams and $lines lines. Need 30 teams. Copy the whole page again (Cmd+A, Cmd+C) and rerun."; exit 1; fi
cp /tmp/team_picks_check.txt config/team_picks_raw.txt
echo "Saved $n teams, $lines lines."
git add config/team_picks_raw.txt
git commit -m "Update team future picks" || echo "no changes"
git push
