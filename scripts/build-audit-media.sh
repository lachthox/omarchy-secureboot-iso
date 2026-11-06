#!/usr/bin/env bash
source scripts/common.sh
cloud_only
mkdir -p out/hardware-validation out/secure-live work/secure-live
python3 scripts/prepare-secure-live.py --mode audit
root=$PWD/work/secure-live
trap 'rm -f -- "$root/release.key"' EXIT
umask 077
openssl req -new -x509 -newkey rsa:3072 -nodes -days 3650 \
  -subj "/CN=Omarchy audit media run $GITHUB_RUN_ID/" \
  -keyout "$root/release.key" -out "$root/release.pem"
openssl x509 -in "$root/release.pem" -outform DER -out "$root/omarchy-live.cer"
/usr/lib/systemd/ukify build --linux="$root/vmlinuz" --initrd="$root/authenticated-initrd" \
  --cmdline="@$root/cmdline" --os-release="@$root/os-release" --sign-kernel \
  --secureboot-private-key="$root/release.key" --secureboot-certificate="$root/release.pem" --output="$root/grubx64.efi"
sbverify --cert "$root/release.pem" "$root/grubx64.efi"
truncate -s 512M "$root/esp.img"
mkfs.fat -F32 -n OMARCHY_SB "$root/esp.img"
mmd -i "$root/esp.img" ::/EFI ::/EFI/BOOT
for pair in 'shimx64.efi:BOOTX64.EFI' 'mmx64.efi:mmx64.efi'; do
  mcopy -i "$root/esp.img" "work/installed-tools/${pair%:*}" "::/EFI/BOOT/${pair#*:}"
done
for file in grubx64.efi omarchy-live.cer; do mcopy -i "$root/esp.img" "$root/$file" "::/EFI/BOOT/$file"; done
# Replay the original hybrid/BIOS equipment. Replace only the appended EFI
# partition and its El Torito reference, with an explicitly audited larger ESP.
xorriso -indev out/image/omarchy-custom-diagnostic.iso \
  -outdev out/hardware-validation/omarchy-hardware-validation.iso \
  -boot_image any replay \
  -append_partition 2 0xef "$root/esp.img" \
  -boot_image any efi_path=--interval:appended_partition_2:all:: \
  -boot_image any emul_type=no_emulation -boot_image any load_size=full \
  -map work/installed-tools/shimx64.efi /EFI/BOOT/BOOTx64.EFI \
  -map work/installed-tools/mmx64.efi /EFI/BOOT/mmx64.efi \
  -map "$root/grubx64.efi" /EFI/BOOT/grubx64.efi \
  -map "$root/omarchy-live.cer" /EFI/BOOT/omarchy-live.cer \
  -commit -end
xorriso -indev out/hardware-validation/omarchy-hardware-validation.iso -report_el_torito plain -report_system_area plain > out/secure-live/audit-boot-structures.txt 2>&1
python3 - <<'PY'
import base64,hashlib,json,os,pathlib,subprocess
root=pathlib.Path('out/hardware-validation')
metadata=json.load(open('out/image/build-metadata.json'))
cert=pathlib.Path('work/secure-live/omarchy-live.cer').read_bytes()
metadata.update(profile='hardware-validation',secure_boot_supported=True,
    physical_installation_enabled=False,physical_installation_validated=False,
    certificate_der_base64=base64.b64encode(cert).decode(),certificate_sha256=hashlib.sha256(cert).hexdigest(),
    live_root=json.load(open('out/secure-live/payloads.json')),
    boot_chain='Microsoft-signed shim -> owner-enrolled signed UKI -> authenticated RAM SquashFS',
    key_management='One-build live signing key discarded; only public certificate distributed')
(root/'build-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
report=pathlib.Path('out/secure-live/audit-boot-structures.txt').read_text()
for marker in ('BIOS','UEFI','MBR isohybrid','GPT',"Volume id    : 'OMARCHY_202610'"):
    assert marker in report,marker
PY
(cd out/hardware-validation && sha256sum omarchy-hardware-validation.iso > SHA256SUMS)
rm -f -- "$root/release.key"
