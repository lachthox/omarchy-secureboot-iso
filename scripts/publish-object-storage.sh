#!/usr/bin/env bash
source scripts/common.sh
cloud_only
[[ ${RELEASE_TAG:-} =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]
: "${RELEASE_BUCKET:?Set repository variable RELEASE_BUCKET}"
: "${RELEASE_PUBLIC_BASE_URL:?Set repository variable RELEASE_PUBLIC_BASE_URL}"
: "${AWS_ACCESS_KEY_ID:?Set repository secret RELEASE_ACCESS_KEY_ID}"
: "${AWS_SECRET_ACCESS_KEY:?Set repository secret RELEASE_SECRET_ACCESS_KEY}"
export AWS_DEFAULT_REGION=${RELEASE_REGION:-auto}
export AWS_EC2_METADATA_DISABLED=true
python3 - <<'PY'
import os,re,urllib.parse
assert re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',os.environ['RELEASE_BUCKET'])
for key in ('RELEASE_PUBLIC_BASE_URL','RELEASE_S3_ENDPOINT'):
    value=os.environ.get(key,'')
    if not value: continue
    u=urllib.parse.urlsplit(value)
    assert u.scheme=='https' and u.hostname and not u.username and not u.password and not u.query and not u.fragment, 'Invalid '+key
PY
mapfile -t images < <(find release -maxdepth 1 -type f -name '*.iso')
[[ ${#images[@]} == 1 ]]
iso=${images[0]}
filename=$(basename "$iso")
[[ $filename =~ ^[a-zA-Z0-9._-]+\.iso$ ]]
hash=$(sha256sum "$iso" | awk '{print $1}')
key="releases/$RELEASE_TAG/$hash/$filename"
url="${RELEASE_PUBLIC_BASE_URL%/}/$key"
endpoint=()
if [[ -n ${RELEASE_S3_ENDPOINT:-} ]]; then endpoint=(--endpoint-url "$RELEASE_S3_ENDPOINT"); fi
aws --version > release/storage-tool-version.txt
# Content-addressed, versioned keys preserve old release URLs. Re-runs upload
# identical verified bytes. Bucket versioning/object lock may add protection.
aws "${endpoint[@]}" s3 cp "$iso" "s3://$RELEASE_BUCKET/$key" \
  --only-show-errors --no-follow-symlinks --content-type application/octet-stream \
  --cache-control 'public,max-age=31536000,immutable' --metadata "sha256=$hash"
# Verify actual PUBLIC bytes on the cloud runner. ETag is not a SHA256 and
# uploader-supplied metadata is not independent verification of remote contents.
actual=$(curl --proto '=https' --tlsv1.2 -fL --retry 3 "$url" | sha256sum | awk '{print $1}')
[[ $actual == "$hash" ]] || { echo 'Public object failed SHA256 verification' >&2; exit 1; }
printf '%s\n' "$url" > release/iso-download-url.txt
aws "${endpoint[@]}" s3 cp release/SHA256SUMS "s3://$RELEASE_BUCKET/releases/$RELEASE_TAG/$hash/SHA256SUMS" --only-show-errors
aws "${endpoint[@]}" s3 cp release/build-metadata.json "s3://$RELEASE_BUCKET/releases/$RELEASE_TAG/$hash/build-metadata.json" --only-show-errors
