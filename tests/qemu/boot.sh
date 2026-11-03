#!/usr/bin/env bash
source scripts/common.sh
cloud_only
mkdir -p work/vm out/qemu
(cd out/image && sha256sum -c SHA256SUMS)
python3 tests/qemu/create-fixtures.py
sha256sum work/vm/windows-system.raw work/vm/windows-data.raw > out/qemu/protected-before.sha256
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
accel=(-accel tcg -cpu max)
if [[ -c /dev/kvm ]]; then sudo chmod a+rw /dev/kvm; accel=(-accel kvm -cpu host); fi
set +e
timeout 600 qemu-system-x86_64 -machine q35 "${accel[@]}" -m 6144 -smp 4 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive if=pflash,format=raw,file=work/vm/vars.fd \
  "${media[@]}" "${disks[@]}" -boot d -display none -serial file:out/qemu/serial.log -monitor none -nic none -no-reboot \
  > out/qemu/qemu.log 2>&1
status=$?
set -e
sha256sum -c out/qemu/protected-before.sha256 > out/qemu/protected-after.txt
[[ $status == 0 ]] || { cat out/qemu/qemu.log; tail -80 out/qemu/serial.log; exit "$status"; }
grep -q 'OMARCHY_CUSTOM_UEFI_BOOT_OK' out/qemu/serial.log
grep -q 'UPSTREAM_INSTALLER_AND_CIDATA_PRESENT' out/qemu/serial.log
printf 'UEFI boot and installer/cidata presence passed; protected fixture bytes unchanged. No installation was performed.\n' > out/qemu/result.txt
