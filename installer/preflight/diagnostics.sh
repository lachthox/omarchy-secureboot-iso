#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /dev/ttyS0) 2>&1
echo 'OMARCHY_CUSTOM_DIAGNOSTICS_STARTED'
[[ -d /sys/firmware/efi ]]
[[ -x /root/configurator && -x /usr/local/bin/omarchy-iso-install ]]
[[ -x /usr/local/bin/omarchy-cidata-load ]]
[[ -d /usr/share/omarchy-iso/orchestrator ]]
echo 'UPSTREAM_INSTALLER_AND_CIDATA_PRESENT'
lsblk --json --bytes -O
echo 'OMARCHY_CUSTOM_UEFI_BOOT_OK'
echo 'Diagnostic boot only. Installer and disk-writing paths have NOT been tested.'
sync
systemctl --no-block poweroff
