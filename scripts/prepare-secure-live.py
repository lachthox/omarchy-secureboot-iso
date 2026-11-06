#!/usr/bin/env python3
"""Create an ephemeral test UKI from the actual official-ISO-derived payloads.

The original initramfs is retained. A small trusted overlay authenticates the
RAM copy of the actual mounted live root before switch_root can execute it.
This deliberately requires copytoram, avoiding a check/use race on USB bytes.
"""
import hashlib
import argparse
import json
import os
import pathlib
import re
import subprocess

assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
parser = argparse.ArgumentParser()
parser.add_argument('--mode',choices=('ci','audit'),default='ci')
args = parser.parse_args()
ROOT = pathlib.Path('work/secure-live'); ROOT.mkdir(parents=True, exist_ok=True)
REPORT = pathlib.Path('out/secure-live'); REPORT.mkdir(parents=True, exist_ok=True)
ISO = 'out/image/omarchy-custom-diagnostic.iso'


def extract(source, name):
    p = ROOT/name
    subprocess.run(['xorriso', '-osirrox', 'on', '-indev', ISO, '-extract', source, str(p)], check=True)
    return p


def archive(data, offset=0):
    result = {}
    while data[offset:offset+6] == b'070701':
        fields = [int(data[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
        size, namesize = fields[6], fields[11]
        start = offset+110
        name = data[start:start+namesize-1].decode()
        content = (start+namesize+3)//4*4
        end = content+size
        offset = (end+3)//4*4
        if name == 'TRAILER!!!':
            return result, offset
        result[name.lstrip('./')] = data[content:end]
    raise RuntimeError('Malformed NEWC archive')


def cpio(files):
    output = bytearray()
    for index, (name, mode, data) in enumerate(files+[('TRAILER!!!', 0, b'')]):
        name = name.encode()+b'\0'
        fields = [index+1, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name), 0]
        output += b'070701'+''.join(f'{n:08x}' for n in fields).encode()+name
        output += b'\0'*(-len(output)%4)
        output += data
        output += b'\0'*(-len(output)%4)
    return bytes(output)


grub = extract('/boot/grub/grub.cfg', 'grub.cfg').read_text()
entry = re.search(r"menuentry[^\n]*--id 'archlinux'[^\n]*\{(.*?)\n\}", grub, re.S)
assert entry
linux = re.search(r'^\s*linux\s+(\S+)\s+(.*)$', entry[1], re.M)
initrd = re.search(r'^\s*initrd\s+(\S+)', entry[1], re.M)
assert linux and initrd and '$' not in linux[1]+initrd[1], 'Unsupported variable kernel path'
kernel = extract(linux[1], 'vmlinuz')
ramdisk = extract(initrd[1], 'original-initrd')
sfs = extract('/arch/x86_64/airootfs.sfs', 'airootfs.sfs')
expected = hashlib.file_digest(sfs.open('rb'), 'sha256').hexdigest()
expected512 = hashlib.file_digest(sfs.open('rb'), 'sha512').hexdigest()
data = ramdisk.read_bytes()
# Walk archive boundaries, never scan for compression magic inside firmware
# blobs: the ISO contains compressed files inside its early/main archives.
contents = {}; offset = 0; layout = []
while offset < len(data):
    while offset < len(data) and data[offset] == 0:
        offset += 1
    if offset == len(data):
        break
    layout.append({'offset': offset, 'magic': data[offset:offset+16].hex()})
    (REPORT/'initramfs-layout.json').write_text(json.dumps(layout, indent=2)+'\n')
    if data[offset:offset+6] == b'070701':
        files, offset = archive(data, offset)
        contents.update(files)
    else:
        if data[offset:offset+4] == b'\x28\xb5\x2f\xfd':
            unpacked = subprocess.check_output(['zstd', '-dc'], input=data[offset:])
        elif data[offset:offset+2] == b'\x1f\x8b':
            import gzip
            unpacked = gzip.decompress(data[offset:])
        elif data[offset:offset+6] == b'\xfd7zXZ\x00':
            import lzma
            unpacked = lzma.decompress(data[offset:])
        else:
            raise RuntimeError('Unsupported initramfs compression/layout')
        files, _ = archive(unpacked)
        contents.update(files)
        break
init = contents['init'].decode()
(REPORT/'original-init').write_text(init)
for name in ('config', 'hooks/archiso'):
    if name in contents:
        (REPORT/name.replace('/', '-')).write_bytes(contents[name])
archiso = contents['hooks/archiso'].decode()
anchor = '    img_loopdev="$(losetup --find --show --read-only -- "${img}")"'
assert archiso.count(anchor) == 1, 'Unsupported ArchISO root mount path'
check = '''    /omarchy-auth-root "$img" || {
        echo 'OMARCHY_LIVE_ROOT_AUTHENTICATION_FAILED' >/dev/console
        poweroff -f
        while :; do sleep 60; done
    }
'''
archiso = archiso.replace(anchor, check+anchor)
auth = '''#!/usr/bin/ash
set -eu
[ "$#" = 1 ] && [ "$1" = /run/archiso/copytoram/airootfs.sfs ] || exit 1
grep -q '^copytoram /run/archiso/copytoram tmpfs ' /proc/mounts || exit 1
echo 'EXPECTED  '"$1" | sha512sum -c - || exit 1
echo 'OMARCHY_AUTHENTICATED_LIVE_ROOT_OK' >/dev/console
'''.replace('EXPECTED', expected512)
overlay = cpio([('hooks/archiso', 0o100755, archiso.encode()), ('omarchy-auth-root', 0o100755, auth.encode())])
(ROOT/'authenticated-initrd').write_bytes(data+b'\0'*(-len(data)%4)+overlay)
words = [w for w in linux[2].split() if w not in ('quiet', 'splash') and not w.startswith(('copytoram=', 'console='))]
words += ['copytoram=y','module.sig_enforce=1','lockdown=integrity',
          'systemd.gpt_auto=0','rd.systemd.gpt_auto=0']
if args.mode == 'ci':
    words += ['console=ttyS0,115200','omarchy_ci=1','systemd.mask=getty@tty1.service',
              'systemd.mask=serial-getty@ttyS0.service']
else:
    words += ['console=tty0','console=ttyS0,115200','omarchy_audit=1',
              'systemd.mask=serial-getty@ttyS0.service','systemd.journald.forward_to_console=yes']
(ROOT/'cmdline').write_text(' '.join(words)+'\n')
(ROOT/'os-release').write_text('ID=omarchy\nNAME="Omarchy Secure Boot cloud acceptance"\n')
(REPORT/'payloads.json').write_text(json.dumps({'kernel_source': linux[1], 'initramfs_source': initrd[1],
    'squashfs_sha256': expected, 'squashfs_sha512': expected512,
    'external_root_policy': 'Authenticate immutable RAM copy before mounting SquashFS',
    'mode':args.mode,'production_boot_chain_validated': False}, indent=2)+'\n')
