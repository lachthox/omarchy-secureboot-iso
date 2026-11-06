#!/usr/bin/env bash
set -euo pipefail
if ! grep -Eq '/omarchy-guarded-[[:digit:]]+\.service($|/)' /proc/self/cgroup; then
  echo 'Use the guarded Omarchy setup wizard. Direct unattended installation is disabled.' >&2
  exit 1
fi
exec /usr/local/lib/omarchy-upstream/omarchy-iso-install "$@"
