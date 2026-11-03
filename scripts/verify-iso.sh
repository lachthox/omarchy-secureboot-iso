#!/usr/bin/env bash
source scripts/common.sh
cloud_only
(cd out/image && sha256sum -c SHA256SUMS)
xorriso -indev out/image/omarchy-custom-diagnostic.iso -report_el_torito plain -report_system_area plain > out/rebuilt-boot.txt 2>&1
python3 - <<'PY'
import pathlib, re, subprocess, hashlib
a=pathlib.Path('out/inspection/boot-structures.txt').read_text(); b=pathlib.Path('out/rebuilt-boot.txt').read_text()
for token in ('MBR isohybrid', 'GPT', 'BIOS', 'UEFI', "Volume id    : 'OMARCHY_202610'"):
    assert token in a and token in b, f'Boot structure changed: {token}'
def esp(path, report):
    m=re.search(r'EFI image start and size: (\d+) \* 2048 , (\d+) \* 512',report)
    assert m
    with open(path,'rb') as f:
        f.seek(int(m[1])*2048); data=f.read(int(m[2])*512)
    return hashlib.sha256(data).hexdigest()
assert esp('work/source/upstream.iso',a)==esp('out/image/omarchy-custom-diagnostic.iso',b), 'Hidden ESP changed'
pathlib.Path('out/boot-verification.txt').write_text('Hybrid MBR/GPT and BIOS/UEFI entries retained. Appended ESP byte-identical.\n')
PY
