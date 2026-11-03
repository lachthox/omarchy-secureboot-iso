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
sudo apt-get update -qq
# Only the disposable GitHub-hosted runner is affected. Unavailable locked
# versions fail instead of silently changing the ISO transformation toolchain.
sudo apt-get install -y --no-install-recommends --allow-downgrades "${packages[@]}"
