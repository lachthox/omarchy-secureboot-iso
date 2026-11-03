"""Inspect EFI/PE signatures and the hidden FAT ESP without executing payloads."""
import json
import os
import pathlib
import re
import shutil
import subprocess

assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
out=pathlib.Path('out/inspection/efi'); out.mkdir(parents=True,exist_ok=True)
report=pathlib.Path('out/inspection/boot-structures.txt').read_text()
match=re.search(r'EFI image start and size: (\d+) \* 2048 , (\d+) \* 512',report)
assert match, 'Expected hidden appended EFI image'
offset=int(match[1])*2048; length=int(match[2])*512
source=pathlib.Path('work/source/upstream.iso'); esp=pathlib.Path('work/efi-appended.img')
assert 0<length<=128*1024**2 and offset+length<=source.stat().st_size
with source.open('rb') as src,esp.open('wb') as dst:
    src.seek(offset); dst.write(src.read(length))
listing=subprocess.run(['mdir','-i',str(esp),'::/EFI/BOOT'],capture_output=True,text=True)
(out/'appended-esp-files.txt').write_text(listing.stdout+listing.stderr)
assert listing.returncode==0, 'Appended ESP has an unexpected EFI directory'
results=[]
for p in pathlib.Path('work/iso/EFI/BOOT').glob('*'):
    if p.suffix.lower()!='.efi': continue
    item={'path':str(p.relative_to('work/iso'))}
    for command,key in ((['file',str(p)],'file'),(['sbverify','--list',str(p)],'pe_signatures'),(['objdump','-h',str(p)],'sections')):
        r=subprocess.run(command,capture_output=True,text=True)
        item[key]={'returncode':r.returncode,'output':r.stdout+r.stderr}
    results.append(item)
(out/'efi-audit.json').write_text(json.dumps({'appended_esp_bytes':length,'efi_files':results,
    'firmware_trust_established':False,'note':'PE signature presence alone does not establish firmware trust or downstream verification.'},indent=2)+'\n')
for p in pathlib.Path('work/iso/arch/boot/x86_64').glob('*'):
    r=subprocess.run(['file',str(p)],capture_output=True,text=True)
    with (out/'kernel-initramfs-types.txt').open('a') as f: f.write(r.stdout+r.stderr)
with pathlib.Path('out/inspection/report.md').open('a') as f:
    f.write('\nEFI audit: appended FAT ESP directory and PE signature/section reports are in efi/. Firmware trust is not inferred from signature-table presence.\n')
esp.unlink()
