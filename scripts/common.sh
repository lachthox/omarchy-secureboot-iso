#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
cloud_only() {
  [[ ${GITHUB_ACTIONS:-} == true && ${RUNNER_ENVIRONMENT:-} == github-hosted ]] || {
    echo 'ISO operations are restricted to GitHub-hosted Actions runners.' >&2; exit 1;
  }
}
preflight() {
  cloud_only
  mkdir -p out work
  { date -u --iso-8601=seconds; df -B1 .; free -b; lscpu; } > out/runner-resources.txt
  local available
  available=$(df -PB1 . | awk 'NR==2 {print $4}')
  (( available >= ${MIN_FREE_BYTES:-28000000000} )) || {
    echo "Insufficient disk: $available available; need ${MIN_FREE_BYTES:-28000000000}. See runner-resources.txt." >&2; exit 1;
  }
}
