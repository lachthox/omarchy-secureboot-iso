#!/usr/bin/env bash
# Sourced by the existing QEMU harness before its regular-file fixtures are removed.
[[ $SCENARIO == wizard-signed ]]
grep -q ACTUAL_SIGNED_UPDATE_AND_SIGNING_FAILURE_RECOVERY_PASSED "$report/installed-serial.log"
python3 - "$report" <<'PY'
import base64, pathlib, re, sys
report = pathlib.Path(sys.argv[1])
matches = re.findall(rb'OMARCHY_CI_MOK_DER=([A-Za-z0-9+/=]+)', (report/'installed-serial.log').read_bytes())
assert len(matches) == 1, 'Expected exactly one public VM certificate'
(report/'owner.der').write_bytes(base64.b64decode(matches[0], validate=True))
PY
openssl x509 -inform DER -in "$report/owner.der" -out work/vm/owner.pem
work/secureboot-tools/bin/virt-fw-vars --input /usr/share/OVMF/OVMF_VARS_4M.ms.fd \
  --output-json "$report/baseline-firmware.json"
work/secureboot-tools/bin/virt-fw-vars --input /usr/share/OVMF/OVMF_VARS_4M.ms.fd \
  --output work/vm/signed-vars.fd --add-mok dcf13531-f232-4bb9-8efc-c0c16bcf7f24 work/vm/owner.pem --secure-boot \
  --output-json "$report/mok-firmware.json"
python3 - "$report" <<'PY'
import json, pathlib, sys
report = pathlib.Path(sys.argv[1])
def platform(name):
    return {v['name']:v for v in json.loads((report/name).read_text())['variables'] if v['name'] in ('PK','KEK','db','dbx')}
assert platform('baseline-firmware.json') == platform('mok-firmware.json')
PY
signed_boot() {
  local name=$1
  cp work/vm/signed-vars.fd work/vm/vars.fd
  python3 tests/qemu/boot-installed.py --scenario wizard-signed --log "$report/$name-serial.log" -- \
    qemu-system-x86_64 -machine q35,smm=on "${accel[@]}" -m 8192 -smp 4 \
    -global driver=cfi.pflash01,property=secure,value=on \
    -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd \
    -drive if=pflash,format=raw,file=work/vm/vars.fd "${disks[@]}" "${installed_shares[@]}" \
    -boot c -display none -serial stdio -monitor none -nic none -no-reboot \
    > "$report/$name-qemu.log" 2>&1
  grep -q INSTALLED_SECUREBOOT_1_SETUPMODE_0_INTEGRITY_ENFORCED "$report/$name-serial.log"
  grep -q OMARCHY_INSTALLED_UEFI_BOOT_OK "$report/$name-serial.log"
  ! grep -q OMARCHY_INSTALLED_BOOT_FAILED "$report/$name-serial.log"
}
signed_boot signed-current
# Only the disposable target image is edited. The ESP starts at sector 2048.
esp=work/vm/target.raw@@1048576
mcopy -i "$esp" ::/EFI/Linux/omarchy-current.efi work/vm/current.efi
printf 'tampered embedded initramfs\n' > work/vm/tamper
objcopy --update-section .initrd=work/vm/tamper work/vm/current.efi work/vm/tampered.efi
mcopy -o -i "$esp" work/vm/tampered.efi ::/EFI/BOOT/grubx64.efi
cp work/vm/signed-vars.fd work/vm/vars.fd
set +e
timeout 30 qemu-system-x86_64 -machine q35,smm=on "${accel[@]}" -m 8192 -smp 4 \
  -global driver=cfi.pflash01,property=secure,value=on \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd \
  -drive if=pflash,format=raw,file=work/vm/vars.fd "${disks[@]}" \
  -boot c -display none -serial "file:$report/tampered-serial.log" -monitor none -nic none -no-reboot \
  > "$report/tampered-qemu.log" 2>&1
tamper_status=$?
set -e
[[ $tamper_status == 0 || $tamper_status == 124 ]]
grep -Eiq 'Security Violation|Verification failed|Bad shim signature|Access Denied' "$report/tampered-serial.log"
! grep -q OMARCHY_INSTALLED_UEFI_BOOT_OK "$report/tampered-serial.log"
# Recovery is an independently retained stock UKI, not the rejected current.
mcopy -i "$esp" ::/EFI/Linux/omarchy-recovery.efi work/vm/recovery.efi
mcopy -o -i "$esp" work/vm/recovery.efi ::/EFI/BOOT/grubx64.efi
signed_boot signed-recovery
sha256sum -c "$report/protected-before.sha256" > "$report/protected-after-signed-boots.txt"
printf 'Actual encrypted installed-system signing/update, signing-failure preservation, shim/MOK enforcing boot, tamper rejection and independent recovery boot passed. No automatic recovery selector or interactive enrollment was tested.\n' > "$report/signed-result.txt"
