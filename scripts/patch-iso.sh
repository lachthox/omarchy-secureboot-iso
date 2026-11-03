#!/usr/bin/env bash
source scripts/common.sh
cloud_only
# Diagnostic milestone: no upstream installer source is altered.
sudo install -Dm755 installer/preflight/diagnostics.sh work/rootfs/usr/local/bin/omarchy-custom-diagnostics
sudo install -Dm644 configs/omarchy-ci.service work/rootfs/etc/systemd/system/omarchy-ci.service
sudo mkdir -p work/rootfs/etc/systemd/system/multi-user.target.wants
sudo ln -s /etc/systemd/system/omarchy-ci.service work/rootfs/etc/systemd/system/multi-user.target.wants/omarchy-ci.service
sudo install -Dm644 configs/upstream.json work/rootfs/usr/share/omarchy-custom/upstream.json
python3 scripts/patch-grub.py
