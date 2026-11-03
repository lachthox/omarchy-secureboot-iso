#!/usr/bin/env bash
source scripts/common.sh
cloud_only
mkdir -p work/source out
version=$(jq -er .version configs/upstream.json)
url=$(jq -er .url configs/upstream.json)
hash=$(jq -er .sha256 configs/upstream.json)
fingerprint=$(jq -er .signing_fingerprint configs/upstream.json)
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && $hash =~ ^[0-9a-f]{64}$ && $fingerprint =~ ^[A-F0-9]{40}$ ]]
[[ $url == "https://iso.omarchy.org/omarchy-$version.iso" ]]
curl --proto '=https' --tlsv1.2 -fsSL --retry 3 "$(jq -er .release_api configs/upstream.json)" -o out/upstream-release.json
python3 - <<'PY'
import json
c=json.load(open('configs/upstream.json')); r=json.load(open('out/upstream-release.json'))
assert r['tag_name']=='v'+c['version'] and not r['draft'] and not r['prerelease']
assert c['sha256'] in r['body'], 'Pinned SHA256 absent from official release metadata'
assert c['url'] in r['body'], 'Pinned ISO absent from official release metadata'
PY
iso=work/source/upstream.iso
if [[ ! -f $iso ]]; then curl --proto '=https' --tlsv1.2 -fL --retry 3 "$url" -o "$iso"; fi
printf '%s  %s\n' "$hash" "$iso" | sha256sum -c -
# Always reauthenticate cache hits. A checksum is not an authenticity signature.
curl --proto '=https' --tlsv1.2 -fsSL --retry 3 "$url.sha256" -o out/upstream.sha256
grep -Eq "^$hash([[:space:]]|$)" out/upstream.sha256
curl --proto '=https' --tlsv1.2 -fsSL --retry 3 "$url.sig" -o work/source/upstream.iso.sig
export GNUPGHOME
GNUPGHOME=$(mktemp -d)
trap 'rm -rf -- "$GNUPGHOME"' EXIT
chmod 700 "$GNUPGHOME"
curl --proto '=https' --tlsv1.2 -fsSL --retry 3 "https://keys.openpgp.org/vks/v1/by-fingerprint/$fingerprint" -o "$GNUPGHOME/key.asc"
gpg --batch --import "$GNUPGHOME/key.asc"
gpg --batch --status-fd 1 --verify work/source/upstream.iso.sig "$iso" > out/signature-status.txt 2> out/signature-log.txt
awk -v fp="$fingerprint" '$2 == "VALIDSIG" && ($3 == fp || $NF == fp) {ok=1} END {exit !ok}' out/signature-status.txt
sha256sum "$iso" > out/upstream-verified.sha256
