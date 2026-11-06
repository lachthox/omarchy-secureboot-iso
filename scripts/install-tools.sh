#!/usr/bin/env bash
source scripts/common.sh
cloud_only
profile=${1:?Specify inspect, build or test}
specifications=$(python3 - "$profile" <<'PY'
import json,re,sys
c=json.load(open('configs/tools-ubuntu24.json'))
for name in c['profiles'][sys.argv[1]]:
    version=c['packages'][name]
    assert re.fullmatch('[a-z0-9][a-z0-9+.-]*',name)
    assert re.fullmatch('[A-Za-z0-9:+.~_-]+',version)
    print(name+'='+version)
PY
)
mapfile -t packages <<< "$specifications"
(( ${#packages[@]} > 0 ))
sudo apt-get update -qq -o Acquire::ForceIPv4=true -o Acquire::Retries=2 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20
# Only the disposable GitHub-hosted runner is affected. Unavailable locked
# versions fail instead of silently changing the ISO transformation toolchain.
sudo apt-get install -y --no-install-recommends --allow-downgrades -o Acquire::ForceIPv4=true -o Acquire::Retries=2 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20 "${packages[@]}"
