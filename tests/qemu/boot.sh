#!/usr/bin/env bash
source scripts/common.sh
cloud_only
[[ $SCENARIO =~ ^(cdrom|usb|reordered|install)$ ]]
report=out/qemu/$SCENARIO
mkdir -p work/vm out/qemu
mkdir -p "$report"
if [[ ${ISO_PREVERIFIED:-} != 1 ]]; then (cd out/image && sha256sum -c SHA256SUMS); fi
trap 'rm -rf -- work/vm' EXIT
python3 tests/qemu/create-fixtures.py
if [[ $SCENARIO == install ]]; then python3 tests/qemu/make-cidata.py; fi
sha256sum work/vm/windows-system.raw work/vm/windows-data.raw > "$report/protected-before.sha256"
cp /usr/share/OVMF/OVMF_VARS_4M.fd work/vm/vars.fd
disks=(-drive file=work/vm/windows-system.raw,format=raw,if=none,id=a -device virtio-blk-pci,drive=a,serial=WINDOWS_A
       -drive file=work/vm/windows-data.raw,format=raw,if=none,id=b -device virtio-blk-pci,drive=b,serial=WINDOWS_B
       -drive file=work/vm/target.raw,format=raw,if=none,id=c -device virtio-blk-pci,drive=c,serial=OMARCHYTESTC)
if [[ $SCENARIO == reordered ]]; then
  disks=(-drive file=work/vm/target.raw,format=raw,if=none,id=c -device virtio-blk-pci,drive=c,serial=OMARCHYTESTC
         -drive file=work/vm/windows-data.raw,format=raw,if=none,id=b -device virtio-blk-pci,drive=b,serial=WINDOWS_B
         -drive file=work/vm/windows-system.raw,format=raw,if=none,id=a -device virtio-blk-pci,drive=a,serial=WINDOWS_A)
fi
media=(-drive file=out/image/omarchy-custom-diagnostic.iso,media=cdrom,format=raw,readonly=on)
if [[ $SCENARIO == usb ]]; then
  media=(-device qemu-xhci -drive file=out/image/omarchy-custom-diagnostic.iso,format=raw,if=none,id=usb,readonly=on -device usb-storage,drive=usb,bootindex=1)
fi
if [[ $SCENARIO == install ]]; then
  media+=(-drive file=work/vm/cidata.iso,media=cdrom,format=raw,readonly=on)
fi
accel=(-accel tcg -cpu max)
if [[ -c /dev/kvm ]]; then sudo chmod a+rw /dev/kvm; accel=(-accel kvm -cpu host); fi
set +e
timeout "$([[ $SCENARIO == install ]] && echo 1800 || echo 180)" qemu-system-x86_64 -machine q35 "${accel[@]}" -m 8192 -smp 4 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive if=pflash,format=raw,file=work/vm/vars.fd \
  "${media[@]}" "${disks[@]}" -boot d -display none -serial "file:$report/serial.log" -monitor none -nic none -no-reboot \
  > "$report/qemu.log" 2>&1
status=$?
set -e
sha256sum -c "$report/protected-before.sha256" > "$report/protected-after.txt"
[[ $status == 0 ]] || { cat "$report/qemu.log"; tail -80 "$report/serial.log"; exit "$status"; }
grep -q 'OMARCHY_CUSTOM_UEFI_BOOT_OK' "$report/serial.log"
grep -q 'UPSTREAM_INSTALLER_AND_CIDATA_PRESENT' "$report/serial.log"
grep -q 'KERNEL_DEVICE_WRITE_BOUNDARY_OK' "$report/serial.log"
if [[ $SCENARIO == install ]]; then
  grep -q 'GUARDED_UPSTREAM_INSTALL_OK' "$report/serial.log"
  printf 'Upstream installation completed in device sandbox; protected bytes unchanged.\n' > "$report/result.txt"
else
  printf 'UEFI boot and kernel device-write boundary passed; protected bytes unchanged. No installation performed.\n' > "$report/result.txt"
fi
