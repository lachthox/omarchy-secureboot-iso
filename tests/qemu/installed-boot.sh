#!/usr/bin/env bash
set -euo pipefail
exec > /dev/ttyS0 2>&1
trap 'echo OMARCHY_INSTALLED_BOOT_FAILED; systemctl --no-block poweroff' ERR
[[ ! -d /run/archiso && -d /sys/firmware/efi ]]
[[ $(findmnt -n -o FSTYPE /) == btrfs ]]
pacman -Q omarchy omarchy-settings
findmnt / /boot
echo 'OMARCHY_INSTALLED_UEFI_BOOT_OK'
python -c 'import termios; termios.tcdrain(1)'
systemctl --no-block poweroff
