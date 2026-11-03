#!/usr/bin/env bash
set -euo pipefail
exec > /dev/ttyS0 2>&1
trap 'journalctl -b --no-pager -u omarchy-ci-installed.service -n 100; echo OMARCHY_INSTALLED_BOOT_FAILED; systemctl --no-block poweroff' ERR
[[ $(cat /sys/class/dmi/id/sys_vendor) == QEMU || $(cat /sys/class/dmi/id/sys_vendor) == Bochs ]]
mkdir -p /run/omarchy-signing-tools
mount -t 9p -o trans=virtio,version=9p2000.L,ro,nodev,nosuid omarchy-signing-tools /run/omarchy-signing-tools
if [[ ! -d /opt/omarchy-ci-tools ]]; then
  cp -a /run/omarchy-signing-tools /opt/omarchy-ci-tools
fi
export PATH="/opt/omarchy-ci-tools/bin:$PATH"
python /opt/omarchy-ci-tools/installed-signed-check.py
echo OMARCHY_INSTALLED_UEFI_BOOT_OK
python -c 'import termios; termios.tcdrain(1)'
systemctl --no-block poweroff
