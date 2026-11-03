#!/usr/bin/env bash
source scripts/common.sh
cloud_only
# Diagnostic milestone: no upstream installer source is altered.
sudo install -Dm755 installer/preflight/diagnostics.sh work/rootfs/usr/local/bin/omarchy-custom-diagnostics
sudo install -Dm644 configs/omarchy-ci.service work/rootfs/etc/systemd/system/omarchy-ci.service
sudo mkdir -p work/rootfs/etc/systemd/system/multi-user.target.wants
sudo ln -s /etc/systemd/system/omarchy-ci.service work/rootfs/etc/systemd/system/multi-user.target.wants/omarchy-ci.service
sudo install -Dm644 configs/upstream.json work/rootfs/usr/share/omarchy-custom/upstream.json
sudo mkdir -p work/rootfs/opt/omarchy-custom work/rootfs/usr/local/lib/omarchy-ci
sudo cp -a installer configs work/rootfs/opt/omarchy-custom/
sudo chown -R 0:0 work/rootfs/opt/omarchy-custom
sudo install -m644 tests/qemu/guest-guard.py tests/qemu/guest-install.py tests/qemu/offline-keyboard.py tests/qemu/classic-chroot.py work/rootfs/usr/local/lib/omarchy-ci/
python3 scripts/patch-grub.py
python3 - <<'PY'
import hashlib,json,pathlib
files=[p for base in ('installer','configs') for p in pathlib.Path(base).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
pathlib.Path('out/injected-files.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},indent=2)+'\n')
PY
