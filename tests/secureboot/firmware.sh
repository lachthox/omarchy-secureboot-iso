#!/usr/bin/env bash
source scripts/common.sh
cloud_only
mkdir -p work/secureboot out/secureboot
root=$PWD/work/secureboot
trap 'rm -f -- "$root/owner.key"' EXIT
umask 077
openssl req -new -x509 -newkey rsa:3072 -nodes -days 1 -subj '/CN=Ephemeral CI firmware test only/' -keyout "$root/owner.key" -out "$root/owner.pem"
for kind in loader payload; do
  args=(); [[ $kind != payload ]] || args=(-DPAYLOAD)
  gcc -I/usr/include/efi -I/usr/include/efi/x86_64 -fpic -fshort-wchar -mno-red-zone -fno-stack-protector -fno-strict-aliasing "${args[@]}" -c tests/secureboot/firmware-fixture.c -o "$root/$kind.o"
  ld -nostdlib -znocombreloc -T /usr/lib/elf_x86_64_efi.lds -shared -Bsymbolic /usr/lib/crt0-efi-x86_64.o "$root/$kind.o" -L/usr/lib -lefi -lgnuefi -o "$root/$kind.so"
  objcopy -j .text -j .sdata -j .data -j .dynamic -j .dynsym -j .rel -j .rela -j .reloc --target=efi-app-x86_64 "$root/$kind.so" "$root/$kind.unsigned.efi"
done
printf 'synthetic kernel bytes\n' > "$root/linux"
printf 'synthetic embedded initramfs bytes\n' > "$root/initrd"
printf 'synthetic embedded command line\n' > "$root/cmdline"
objcopy --add-section .linux="$root/linux" --change-section-vma .linux=0x20000 \
  --add-section .initrd="$root/initrd" --change-section-vma .initrd=0x30000 \
  --add-section .cmdline="$root/cmdline" --change-section-vma .cmdline=0x40000 \
  "$root/payload.unsigned.efi" "$root/sectioned.efi"
for kind in loader sectioned; do
  source_file="$root/$kind.efi"; [[ $kind != loader ]] || source_file="$root/loader.unsigned.efi"
  sbsign --key "$root/owner.key" --cert "$root/owner.pem" --output "$root/$kind.signed.efi" "$source_file"
  sbverify --cert "$root/owner.pem" "$root/$kind.signed.efi"
done
work/secureboot-tools/bin/virt-fw-vars --input /usr/share/OVMF/OVMF_VARS_4M.ms.fd \
  --output "$root/enrolled.fd" --add-db 5d5e1358-90f0-4da1-938d-c989965e8d12 "$root/owner.pem" --secure-boot \
  --output-json out/secureboot/firmware-test-vars.json
accel=(-accel tcg -cpu max)
if [[ -c /dev/kvm ]]; then sudo chmod a+rw /dev/kvm; accel=(-accel kvm -cpu host); fi
for scenario in valid unsigned tampered-linux tampered-initrd tampered-cmdline missing-current unsigned-recovery; do
  report=out/secureboot/$scenario; mkdir -p "$report"
  cp "$root/enrolled.fd" "$root/vars.fd"
  truncate -s 64M "$root/esp.img"
  mkfs.fat -F32 "$root/esp.img"
  mmd -i "$root/esp.img" ::/EFI ::/EFI/BOOT ::/EFI/Linux
  mcopy -i "$root/esp.img" "$root/loader.signed.efi" ::/EFI/BOOT/BOOTX64.EFI
  cp "$root/sectioned.signed.efi" "$root/current.efi"
  if [[ $scenario == unsigned ]]; then cp "$root/sectioned.efi" "$root/current.efi"; fi
  if [[ $scenario == tampered-* ]]; then
    printf 'attacker replaced this authenticated section\n' > "$root/changed"
    objcopy --update-section ".${scenario#tampered-}=$root/changed" "$root/current.efi"
  fi
  if [[ $scenario != missing-current && $scenario != unsigned-recovery ]]; then
    mcopy -i "$root/esp.img" "$root/current.efi" ::/EFI/Linux/omarchy-current.efi
  fi
  recovery="$root/sectioned.signed.efi"
  if [[ $scenario == unsigned-recovery ]]; then recovery="$root/sectioned.efi"; fi
  mcopy -i "$root/esp.img" "$recovery" ::/EFI/Linux/omarchy-recovery.efi
  timeout 60 qemu-system-x86_64 -machine q35,smm=on "${accel[@]}" -m 256 \
    -global driver=cfi.pflash01,property=secure,value=on \
    -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd \
    -drive if=pflash,format=raw,file="$root/vars.fd" \
    -drive file="$root/esp.img",format=raw -display none -serial "file:$report/serial.log" -monitor none -nic none -no-reboot > "$report/qemu.log" 2>&1
  grep -q FIRMWARE_SECUREBOOT_1_SETUPMODE_0 "$report/serial.log"
  case $scenario in
    valid) grep -q STARTING_VERIFIED_CURRENT "$report/serial.log" ;;
    unsigned|tampered-*)
      grep -q FIRMWARE_REJECTED_CURRENT "$report/serial.log"
      grep -q STARTING_VERIFIED_RECOVERY "$report/serial.log" ;;
    missing-current) grep -q STARTING_VERIFIED_RECOVERY "$report/serial.log" ;;
    unsigned-recovery)
      grep -q FIRMWARE_REJECTED_RECOVERY "$report/serial.log"
      grep -q NO_VERIFIED_BOOT_IMAGE "$report/serial.log"
      ! grep -q VERIFIED_PAYLOAD_EXECUTED "$report/serial.log" ;;
  esac
  if [[ $scenario != unsigned-recovery ]]; then grep -q VERIFIED_PAYLOAD_EXECUTED "$report/serial.log"; fi
  printf '%s: actual firmware enforcement passed (synthetic EFI fixture, not the Omarchy boot chain).\n' "$scenario" | tee "$report/result.txt"
done
