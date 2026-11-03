#!/usr/bin/env bash
source scripts/common.sh
cloud_only
mkdir -p out/secure-live work/secure-live work/vm
(cd out/image && sha256sum -c SHA256SUMS)
python3 scripts/prepare-secure-live.py
root=$PWD/work/secure-live
cleanup() {
  result=$?
  if [[ -f out/secure-live/before.sha256 ]]; then
    sha256sum -c out/secure-live/before.sha256 > out/secure-live/final-protected.txt || result=1
  fi
  rm -f -- "$root/owner.key"
  rm -rf -- work/vm
  trap - EXIT
  exit "$result"
}
trap cleanup EXIT
umask 077
openssl req -new -x509 -newkey rsa:3072 -nodes -days 1 -subj '/CN=Ephemeral Omarchy live CI only/' -keyout "$root/owner.key" -out "$root/owner.pem"
/usr/lib/systemd/ukify build --linux="$root/vmlinuz" --initrd="$root/authenticated-initrd" \
  --cmdline="@$root/cmdline" --os-release="@$root/os-release" --sign-kernel=yes \
  --secureboot-private-key="$root/owner.key" --secureboot-certificate="$root/owner.pem" --output="$root/live.efi"
sbverify --cert "$root/owner.pem" "$root/live.efi"
work/secureboot-tools/bin/virt-fw-vars --input /usr/share/OVMF/OVMF_VARS_4M.ms.fd \
  --output "$root/vars-template.fd" --add-db dcf13531-f232-4bb9-8efc-c0c16bcf7f24 "$root/owner.pem" --secure-boot \
  --output-json out/secure-live/test-firmware.json
truncate -s 512M "$root/esp.img"
mkfs.fat -F32 -n OMARCHY_SB "$root/esp.img"
mmd -i "$root/esp.img" ::/EFI ::/EFI/BOOT
mcopy -i "$root/esp.img" "$root/live.efi" ::/EFI/BOOT/BOOTX64.EFI
SCENARIO=cdrom python3 tests/qemu/create-fixtures.py
sha256sum work/vm/windows-system.raw work/vm/windows-data.raw > out/secure-live/before.sha256
accel=(-accel tcg -cpu max)
if [[ -c /dev/kvm ]]; then sudo chmod a+rw /dev/kvm; accel=(-accel kvm -cpu host); fi
cp "$root/vars-template.fd" "$root/vars.fd"
timeout 300 qemu-system-x86_64 -machine q35,smm=on "${accel[@]}" -m 12288 -smp 4 \
  -global driver=cfi.pflash01,property=secure,value=on \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd \
  -drive if=pflash,format=raw,file="$root/vars.fd" \
  -drive file="$root/esp.img",format=raw,if=none,id=sb,readonly=on -device virtio-blk-pci,drive=sb,serial=OMARCHY_SB_TEST,bootindex=1 \
  -drive file=out/image/omarchy-custom-diagnostic.iso,format=raw,media=cdrom,readonly=on \
  -drive file=work/vm/windows-system.raw,format=raw,if=none,id=a -device virtio-blk-pci,drive=a,serial=WINDOWS_A \
  -drive file=work/vm/windows-data.raw,format=raw,if=none,id=b -device virtio-blk-pci,drive=b,serial=WINDOWS_B \
  -drive file=work/vm/target.raw,format=raw,if=none,id=c -device virtio-blk-pci,drive=c,serial=OMARCHYTESTC \
  -virtfs "local,path=$PWD/tests/qemu,mount_tag=omarchy-ci,security_model=none,readonly=on" \
  -display none -serial file:out/secure-live/serial.log -monitor none -nic none -no-reboot > out/secure-live/qemu.log 2>&1
grep -q OMARCHY_AUTHENTICATED_LIVE_ROOT_OK out/secure-live/serial.log
grep -q 'LIVE_FIRMWARE SecureBoot=1' out/secure-live/serial.log
grep -q 'LIVE_FIRMWARE SetupMode=0' out/secure-live/serial.log
grep -q UNSIGNED_MODULE_REJECTED_SIGNED_MODULE_ACCEPTED out/secure-live/serial.log
grep -q OMARCHY_CUSTOM_UEFI_BOOT_OK out/secure-live/serial.log
! grep -q OMARCHY_CI_FAILURE out/secure-live/serial.log
sha256sum -c out/secure-live/before.sha256 > out/secure-live/after.txt
printf 'Actual modified-Omarchy kernel/initramfs/root booted under enforcing OVMF; unsigned module control rejected. Direct test-db trust only; consumer shim/MOK remains separate.\n' > out/secure-live/result.txt
