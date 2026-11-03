#!/usr/bin/env bash
source scripts/common.sh
cloud_only
mkdir -p out
df -B1 . > out/space-before-tool-cleanup.txt
# These are preinstalled, unrelated SDKs on the disposable GitHub runner.
# Literal paths only; this script is never invoked on the developer computer.
sudo rm -rf -- /usr/local/lib/android /usr/share/dotnet /opt/ghc /opt/hostedtoolcache/CodeQL
df -B1 . > out/space-after-tool-cleanup.txt
MIN_FREE_BYTES=34000000000 preflight
