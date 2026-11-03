#!/usr/bin/env bash
# Optional POST-INSTALL source/package preparation; never run by the live ISO.
set -euo pipefail
[[ $EUID != 0 ]] || { echo 'Run as an ordinary user; makepkg must not run as root.' >&2; exit 1; }
[[ ! -d /run/archiso ]] || { echo 'Run only on the installed system.' >&2; exit 1; }
[[ -f /etc/arch-release ]]
base=$(cd "$(dirname "$0")/../.." && pwd)
pin=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["revision"])' "$base/configs/gpu-unlock.json")
[[ $pin =~ ^[0-9a-f]{40}$ ]]
python3 - <<'PY'
from pathlib import Path
allowed={('0x10de','0x2484'),('0x10de','0x2488')}
matches=[]
for dev in Path('/sys/bus/pci/devices').glob('*'):
    if not (dev/'vendor').exists() or not (dev/'device').exists(): continue
    pair=((dev/'vendor').read_text().strip(),(dev/'device').read_text().strip())
    if pair in allowed: matches.append(dev.name)
assert matches, 'No reviewed RTX 3070 PCI ID detected; refusing to guess'
print('Compatible RTX 3070 addresses:', ', '.join(matches))
PY
dest=${XDG_CACHE_HOME:-$HOME/.cache}/omarchy-custom/gpu-unlock-$pin
[[ ! -e $dest ]] || { echo "Review existing checkout at $dest instead of overwriting it." >&2; exit 1; }
git clone --no-checkout https://github.com/Zagitta/gpu-unlock "$dest"
git -C "$dest" checkout --detach "$pin"
[[ $(git -C "$dest" rev-parse HEAD) == "$pin" ]]
[[ -z $(git -C "$dest" status --porcelain) ]]
(cd "$dest/packaging/arch" && makepkg --syncdeps --cleanbuild)
echo "Packages prepared in $dest/packaging/arch. No unlock boot option was enabled."
echo 'Follow docs/gpu-unlock.md: preserve stock UKI, configure signing, then add a separate opt-in boot entry.'
