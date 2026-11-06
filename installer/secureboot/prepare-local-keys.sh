#!/usr/bin/env bash
# Installed-system opt-in. Does not modify firmware variables or enroll keys.
set -euo pipefail
[[ $EUID == 0 && ! -d /run/archiso ]]
[[ $# == 1 && $1 == --generate-local-mok ]] || {
  echo 'Usage: sudo bash prepare-local-keys.sh --generate-local-mok'; exit 2;
}
# Credentials must reside on an encrypted installed root, not the ESP or USB.
root_source=$(findmnt -n -o SOURCE / | sed 's/\[.*//')
lsblk -sno TYPE "$root_source" | grep -qx crypt || {
  echo 'An encrypted root filesystem is required for local private-key storage.' >&2; exit 1;
}
dest=/var/lib/omarchy-custom/keys
[[ ! -e $dest ]] || { echo 'Existing keys will not be overwritten.' >&2; exit 1; }
umask 077
install -d -m700 "$dest"
openssl req -new -x509 -newkey rsa:3072 -nodes -days 3650 \
  -subj '/CN=Omarchy machine-local owner key/' \
  -addext 'extendedKeyUsage=codeSigning' \
  -keyout "$dest/MOK.key" -outform DER -out "$dest/MOK.der"
openssl x509 -inform DER -in "$dest/MOK.der" -out "$dest/MOK.pem"
chmod 600 "$dest"/*
openssl x509 -inform DER -in "$dest/MOK.der" -noout -fingerprint -sha256
echo 'Public MOK certificate generated. No key was enrolled and no firmware key was replaced.'
echo 'Enrollment and signing require a verified shim/MOK boot chain; see docs/security-model.md.'
