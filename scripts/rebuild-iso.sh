#!/usr/bin/env bash
source scripts/common.sh
cloud_only
export SOURCE_DATE_EPOCH
SOURCE_DATE_EPOCH=$(git show -s --format=%ct HEAD)
# CPU/RAM bounded; retain ownership, xattrs, special files from root extraction.
sudo mksquashfs work/rootfs work/custom.sfs -noappend -comp zstd -Xcompression-level 6 -b 1M -processors 4 -mem 4G -mkfs-time "$SOURCE_DATE_EPOCH" -all-time "$SOURCE_DATE_EPOCH"
sha512sum work/custom.sfs | sed 's@work/custom.sfs@airootfs.sfs@' > work/airootfs.sha512
mkdir -p out/image
# Replay ORIGINAL boot metadata, including hidden appended ESP and isohybrid MBR/GPT.
# Do not create a new generic mkisofs layout or assume the ESP is an ISO file.
xorriso -indev work/source/upstream.iso -outdev out/image/omarchy-custom-diagnostic.iso \
  -boot_image any replay \
  -map work/custom.sfs /arch/x86_64/airootfs.sfs \
  -map work/airootfs.sha512 /arch/x86_64/airootfs.sha512 \
  -map work/custom-grub.cfg /boot/grub/grub.cfg \
  -commit -end
(cd out/image && sha256sum omarchy-custom-diagnostic.iso > SHA256SUMS)
python3 - <<'PY'
import json, os, pathlib, subprocess
data={'schema':1,'profile':'diagnostic-only','commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
      'run_id':os.environ['GITHUB_RUN_ID'],'upstream':json.load(open('configs/upstream.json')),
      'secure_boot_supported':False,'physical_installation_validated':False,
      'test_harness_protocol':1,
      'compression':'zstd level 6, 1MiB blocks','source_date_epoch':os.environ['SOURCE_DATE_EPOCH']}
data['injected_files']=json.load(open('out/injected-files.json'))
pathlib.Path('out/image/build-metadata.json').write_text(json.dumps(data,indent=2)+'\n')
PY
