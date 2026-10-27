#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

git pull --rebase --quiet
python3 scripts/update_readme_stats.py

if git diff --quiet; then
    exit 0
fi

git commit --quiet -am "chore: refresh readme stats"
for remote in $(git remote); do
    git push --quiet "$remote" HEAD
done
