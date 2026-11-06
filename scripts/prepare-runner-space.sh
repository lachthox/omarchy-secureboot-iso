#!/usr/bin/env bash
source scripts/common.sh
cloud_only
mkdir -p out
df -B1 . > out/space-before-tool-cleanup.txt
# These are preinstalled, unrelated SDKs on the disposable GitHub runner.
# Literal paths only; this script is never invoked on the developer computer.
for unused_sdk in /usr/share/dotnet /opt/ghc /opt/hostedtoolcache/CodeQL /usr/local/lib/android; do
  available=$(df -B1 --output=avail . | tail -1 | tr -d ' ')
  if (( available >= 34000000000 )); then break; fi
  sudo rm -rf -- "$unused_sdk"
done
df -B1 . > out/space-after-tool-cleanup.txt
MIN_FREE_BYTES=34000000000 preflight
