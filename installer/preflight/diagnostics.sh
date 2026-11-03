#!/usr/bin/env bash
set -euo pipefail
exec > /dev/ttyS0 2>&1
trap 'status=$?; echo "OMARCHY_CI_FAILURE status=$status line=$LINENO"; python -c "import termios; termios.tcdrain(1)"; systemctl --no-block poweroff; exit "$status"' ERR
echo 'OMARCHY_CUSTOM_DIAGNOSTICS_STARTED'
[[ -d /sys/firmware/efi ]]
[[ -x /root/configurator && -x /usr/local/bin/omarchy-iso-install ]]
[[ -x /usr/local/bin/omarchy-cidata-load ]]
[[ -d /usr/share/omarchy-iso/orchestrator ]]
echo 'UPSTREAM_INSTALLER_AND_CIDATA_PRESENT'
lsblk --json --bytes -o NAME,TYPE,MODEL,SERIAL,SIZE,FSTYPE,MOUNTPOINTS
if [[ $(cat /sys/class/dmi/id/sys_vendor) == QEMU || $(cat /sys/class/dmi/id/sys_vendor) == Bochs ]]; then
  harness=/usr/local/lib/omarchy-ci
  # CI exposes ONLY repository test sources via a read-only virtio-9p share.
  # This lets test-only edits reuse an existing ISO without extraction/rebuild.
  if modprobe 9pnet_virtio && mkdir -p /run/omarchy-ci && mount -t 9p -o trans=virtio,version=9p2000.L,ro,nodev,nosuid omarchy-ci /run/omarchy-ci; then
    harness=/run/omarchy-ci
    echo 'CURRENT_CI_HARNESS_LOADED'
  fi
  python "$harness/guest-guard.py"
  if [[ -e /dev/disk/by-label/cidata ]]; then
    python "$harness/guest-install.py"
  fi
fi
echo 'OMARCHY_CUSTOM_UEFI_BOOT_OK'
echo 'Experimental image: physical installation and Secure Boot acceptance remain pending.'
python -c 'import termios; termios.tcdrain(1)'
sync
systemctl --no-block poweroff
