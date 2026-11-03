#!/usr/bin/env python3
"""Create an ephemeral test UKI from the actual official-ISO-derived payloads.

The original initramfs is retained. A small trusted overlay authenticates the
RAM copy of the actual mounted live root before switch_root can execute it.
This deliberately requires copytoram, avoiding a check/use race on USB bytes.
"""
import hashlib
import json
import os
import pathlib
import re
import subprocess

assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
ROOT = pathlib.Path('work/secure-live'); ROOT.mkdir(parents=True, exist_ok=True)
REPORT = pathlib.Path('out/secure-live'); REPORT.mkdir(parents=True, exist_ok=True)
ISO = 'out/image/omarchy-custom-diagnostic.iso'


def extract(source, name):
    p = ROOT/name
    subprocess.run(['xorriso', '-osirrox', 'on', '-indev', ISO, '-extract', source, str(p)], check=True)
    return p


def entries(data, offset=0):
    while data[offset:offset+6] == b'070701':
        fields = [int(data[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
        size, namesize = fields[6], fields[11]
        start = offset+110
        name = data[start:start+namesize-1].decode()
        content = (start+namesize+3)//4*4
        end = content+size
        if name == 'TRAILER!!!':
            return
        yield name.lstrip('./'), data[content:end]
        offset = (end+3)//4*4


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
data = ramdisk.read_bytes()
# mkinitcpio may prepend an uncompressed early microcode CPIO. Locate the
# following zstd frame, then parse the decompressed NEWC archive inertly.
if data[:4] == b'\x28\xb5\x2f\xfd':
    compressed = data
elif data[:6] == b'070701':
    magic = data.find(b'\x28\xb5\x2f\xfd')
    assert magic > 0, 'Unsupported initramfs compression'
    compressed = data[magic:]
else:
    raise RuntimeError('Unsupported initramfs compression/layout')
unpacked = subprocess.check_output(['zstd', '-dc'], input=compressed)
contents = dict(entries(unpacked))
init = contents['init'].decode()
(REPORT/'original-init').write_text(init)
for name in ('config', 'hooks/archiso'):
    if name in contents:
        (REPORT/name.replace('/', '-')).write_bytes(contents[name])
assert init.count('exec env -i') == 1 and 'switch_root' in init, 'Unexpected initramfs switch_root implementation'
check = '''
/omarchy-auth-root || {
    echo 'OMARCHY_LIVE_ROOT_AUTHENTICATION_FAILED' >/dev/console
    poweroff -f
    while :; do sleep 60; done
}
'''
init = init.replace('exec env -i', check+'exec env -i')
auth = '''#!/usr/bin/ash
set -eu
count=0
for loop in /sys/block/loop*/loop/backing_file; do
    [ -r "$loop" ] || continue
    source=$(cat "$loop")
    case "$source" in
        *airootfs.sfs)
            case "$source" in
                /run/archiso/copytoram/*) ;;
                *) echo 'UNAUTHENTICATED_EXTERNAL_LIVE_ROOT' >/dev/console; exit 1 ;;
            esac
            [ -f "$source" ] || exit 1
            echo 'EXPECTED  '"$source" | sha256sum -c - || exit 1
            count=$((count+1))
            ;;
    esac
done
[ "$count" = 1 ] || exit 1
echo 'OMARCHY_AUTHENTICATED_LIVE_ROOT_OK' >/dev/console
'''.replace('EXPECTED', expected)
overlay = cpio([('init', 0o100755, init.encode()), ('omarchy-auth-root', 0o100755, auth.encode())])
(ROOT/'authenticated-initrd').write_bytes(data+b'\0'*(-len(data)%4)+overlay)
words = [w for w in linux[2].split() if w not in ('quiet', 'splash') and not w.startswith(('copytoram=', 'console='))]
words += ['copytoram=y', 'console=ttyS0,115200', 'omarchy_ci=1',
          'systemd.mask=getty@tty1.service', 'systemd.mask=serial-getty@ttyS0.service',
          'module.sig_enforce=1', 'lockdown=integrity']
(ROOT/'cmdline').write_text(' '.join(words)+'\n')
(ROOT/'os-release').write_text('ID=omarchy\nNAME="Omarchy Secure Boot cloud acceptance"\n')
(REPORT/'payloads.json').write_text(json.dumps({'kernel_source': linux[1], 'initramfs_source': initrd[1],
    'squashfs_sha256': expected, 'external_root_policy': 'Authenticate immutable RAM copy before switch_root',
    'production_boot_chain_validated': False}, indent=2)+'\n')
