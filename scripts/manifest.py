"""Read inert ISO files and filesystem metadata; never execute upstream code."""
import hashlib
import json
import pathlib
import subprocess

root = pathlib.Path('work/iso')
out = pathlib.Path('out/inspection')
squashes = []
for p in sorted(root.rglob('*')):
    if not p.is_file():
        continue
    with p.open('rb') as f:
        magic = f.read(4)
    if magic != b'hsqs':
        continue
    name = str(p.relative_to(root))
    key = name.replace('/', '_')
    stat = subprocess.run(['unsquashfs', '-s', str(p)], capture_output=True, text=True, check=True).stdout
    listing = subprocess.run(['unsquashfs', '-ll', str(p)], capture_output=True, text=True, check=True).stdout
    (out / (key + '.stat.txt')).write_text(stat)
    (out / (key + '.files.txt')).write_text(listing)
    # Selected source/config files only; unsquashfs -cat does not run them.
    candidates = []
    for line in listing.splitlines():
        if 'squashfs-root/' not in line or not line.startswith('-'):
            continue
        path = line.split('squashfs-root/', 1)[1]
        if any(x in path for x in ('omarchy-iso', 'omarchy-cidata', 'configurator', '.automated_script', 'archinstall', 'limine', 'mkinitcpio')):
            candidates.append(path)
    sources = {}
    for index, path in enumerate(candidates):
        # Limit individual and total inspection output; no opaque binaries.
        result = subprocess.run(['unsquashfs', '-cat', str(p), path], capture_output=True, check=False)
        data = result.stdout
        if result.returncode or len(data) > 1024*1024 or b'\0' in data:
            continue
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            continue
        dest = out / 'sources' / key / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
        sources[path] = hashlib.sha256(data).hexdigest()
    squashes.append({'path': name, 'size': p.stat().st_size, 'stat': stat, 'source_hashes': sources})
efi = [str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.suffix.lower() in ('.efi', '.img')]
manifest = {'schema': 1, 'upstream': json.load(open('configs/upstream.json')), 'squashfs': squashes, 'efi_and_images': efi}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
report = '# Actual upstream ISO inspection\n\n'
report += 'Authenticated via pinned SHA256 and OpenPGP primary fingerprint. No extracted scripts were executed.\n\n'
for s in squashes:
    report += f"* SquashFS: `{s['path']}` ({s['size']} bytes), {len(s['source_hashes'])} source files recorded.\n"
report += '\nSee boot-structures.txt, partitions.txt, files.tsv and sources/ for measured layout and installer implementation.\n'
(out / 'report.md').write_text(report)
assert squashes, 'No SquashFS found: unsupported layout'
