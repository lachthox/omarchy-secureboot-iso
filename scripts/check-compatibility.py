import hashlib
import json
import pathlib
import subprocess

c = json.load(open('configs/compatibility.json'))
u = json.load(open('configs/upstream.json'))
assert c['upstream_sha256'] == u['sha256'], 'New ISO requires a new reviewed compatibility profile'
s = pathlib.Path('work/iso') / c['squashfs_path']
for path, expected in c['installer_hashes'].items():
    data = subprocess.check_output(['unsquashfs', '-cat', str(s), path])
    assert hashlib.sha256(data).hexdigest() == expected, f'Unsupported installer file: {path}'
report = pathlib.Path('out/inspection/boot-structures.txt').read_text()
assert 'MBR isohybrid' in report and 'GPT' in report and 'UEFI' in report
assert 'Found hidden El-Torito image for EFI' in report
pathlib.Path('out/compatibility.json').write_text(json.dumps(c, indent=2)+'\n')
