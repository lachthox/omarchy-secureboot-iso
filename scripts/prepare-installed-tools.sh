#!/usr/bin/env bash
source scripts/common.sh
cloud_only
dest=work/installed-tools
mkdir -p "$dest/runtime" "$dest/bin" "$dest/secureboot"
cp installer/secureboot/*.py installer/secureboot/prepare-local-keys.sh "$dest/secureboot/"
cp tests/qemu/installed-signed-check.py "$dest/"
# Bundle the runner's pinned signing tools with their own ELF loader/libraries.
# The guest uses Arch; it must not resolve Ubuntu binaries against Arch's libc.
for name in sbsign sbverify; do
  binary=$(command -v "$name")
  cp "$binary" "$dest/runtime/$name"
  ldd "$binary" | awk '/=> \// {print $3} /^[[:space:]]*\// {print $1}' |
    while IFS= read -r library; do cp -L "$library" "$dest/runtime/"; done
  cat > "$dest/bin/$name" <<EOF
#!/bin/sh
runtime=\$(CDPATH= cd -- "\$(dirname -- "\$0")/../runtime" && pwd)
exec "\$runtime/ld-linux-x86-64.so.2" --library-path "\$runtime" "\$runtime/$name" "\$@"
EOF
  chmod 755 "$dest/bin/$name"
done
mkdir -p work/installed-shim
(cd work/installed-shim && apt-get download shim-signed=1.58+15.8-0ubuntu1)
dpkg-deb -x work/installed-shim/shim-signed_*.deb work/installed-shim/package
cp work/installed-shim/package/usr/lib/shim/shimx64.efi.signed.latest "$dest/shimx64.efi"
cp work/installed-shim/package/usr/lib/shim/mmx64.efi "$dest/mmx64.efi"
sudo apt-get install -y --no-install-recommends systemd-boot-efi=255.4-1ubuntu8.18
cp /usr/lib/systemd/boot/efi/systemd-bootx64.efi "$dest/systemd-bootx64.efi"
sbverify --list "$dest/shimx64.efi" > out/installed-shim-signatures.txt
grep -q Microsoft out/installed-shim-signatures.txt
cp work/installed-shim/package/usr/share/doc/shim-signed/copyright "$dest/shim-COPYRIGHT"
cp /usr/share/doc/systemd-boot-efi/copyright "$dest/systemd-COPYRIGHT"
