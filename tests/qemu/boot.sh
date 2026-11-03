#!/usr/bin/env bash
source scripts/common.sh
cloud_only
[[ $SCENARIO =~ ^(cdrom|usb|reordered|invalid|install)$ ]]
report=out/qemu/$SCENARIO
mkdir -p work/vm out/qemu
mkdir -p "$report"
if [[ ${ISO_PREVERIFIED:-} != 1 ]]; then (cd out/image && sha256sum -c SHA256SUMS); fi
cleanup() {
  local result=$?
  if [[ -f $report/protected-before.sha256 ]]; then
    sha256sum -c "$report/protected-before.sha256" > "$report/protected-final.txt" || result=1
  fi
  rm -rf -- work/vm
  trap - EXIT
  exit "$result"
}
trap cleanup EXIT
python3 - <<'PY' > "$report/revisions.json"
import json,subprocess
m=json.load(open('out/image/build-metadata.json'))
assert m.get('test_harness_protocol')==1, 'This image predates the fast test interface; rebuild it once'
print(json.dumps({'image_commit':m['commit'],'test_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}))
PY
python3 tests/qemu/create-fixtures.py
if [[ $SCENARIO == install ]]; then python3 tests/qemu/make-cidata.py; fi
sha256sum work/vm/windows-system.raw work/vm/windows-data.raw > "$report/protected-before.sha256"
if [[ $SCENARIO == invalid ]]; then sha256sum work/vm/target.raw >> "$report/protected-before.sha256"; fi
cp /usr/share/OVMF/OVMF_VARS_4M.fd work/vm/vars.fd
target_serial=OMARCHYTESTC
if [[ $SCENARIO == invalid ]]; then target_serial=UNRECOGNIZED; fi
disks=(-drive file=work/vm/windows-system.raw,format=raw,if=none,id=a -device virtio-blk-pci,drive=a,serial=WINDOWS_A
       -drive file=work/vm/windows-data.raw,format=raw,if=none,id=b -device virtio-blk-pci,drive=b,serial=WINDOWS_B
       -drive file=work/vm/target.raw,format=raw,if=none,id=c -device "virtio-blk-pci,drive=c,serial=$target_serial")
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
  -virtfs "local,path=$PWD/tests/qemu,mount_tag=omarchy-ci,security_model=none,readonly=on" \
  > "$report/qemu.log" 2>&1
status=$?
set -e
sha256sum -c "$report/protected-before.sha256" > "$report/protected-after.txt"
[[ $status == 0 ]] || { cat "$report/qemu.log"; tail -80 "$report/serial.log"; exit "$status"; }
if [[ $SCENARIO == invalid ]]; then
  grep -q OMARCHY_CI_FAILURE "$report/serial.log"
  grep -q 'Unexpected guest disks; refusing writes' "$report/serial.log"
  printf 'Unrecognized target refused; every synthetic disk byte unchanged.\n' > "$report/result.txt"
  exit 0
fi
if grep -q OMARCHY_CI_FAILURE "$report/serial.log"; then exit 1; fi
grep -q 'OMARCHY_CUSTOM_UEFI_BOOT_OK' "$report/serial.log"
grep -q 'UPSTREAM_INSTALLER_AND_CIDATA_PRESENT' "$report/serial.log"
grep -q 'CURRENT_CI_HARNESS_LOADED' "$report/serial.log"
grep -q 'KERNEL_DEVICE_WRITE_BOUNDARY_OK' "$report/serial.log"
if [[ $SCENARIO == install ]]; then
  grep -q 'GUARDED_UPSTREAM_INSTALL_OK' "$report/serial.log"
  grep -q 'WINDOWS_NVRAM_ENTRY_PRESERVED' "$report/serial.log"
  timeout 180 qemu-system-x86_64 -machine q35 "${accel[@]}" -m 8192 -smp 4 \
    -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
    -drive if=pflash,format=raw,file=work/vm/vars.fd "${disks[@]}" \
    -boot c -display none -serial "file:$report/installed-serial.log" -monitor none -nic none -no-reboot \
    > "$report/installed-qemu.log" 2>&1
  sha256sum -c "$report/protected-before.sha256" > "$report/protected-after-installed-boot.txt"
  grep -q OMARCHY_INSTALLED_UEFI_BOOT_OK "$report/installed-serial.log"
  if grep -q OMARCHY_INSTALLED_BOOT_FAILED "$report/installed-serial.log"; then exit 1; fi
  printf 'Upstream install and installed-system UEFI boot passed; protected bytes and Windows NVRAM entry unchanged.\n' > "$report/result.txt"
else
  printf 'UEFI boot and kernel device-write boundary passed; protected bytes unchanged. No installation performed.\n' > "$report/result.txt"
fi
