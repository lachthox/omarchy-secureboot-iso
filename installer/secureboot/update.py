#!/usr/bin/env python3
"""Build and validate a machine-local signed UKI before touching active images."""
import argparse
import json
import os
import pathlib
import re
import subprocess
import tempfile

from bootstore import InvalidBootImage, publish

KEYS = pathlib.Path('/var/lib/omarchy-custom/keys')


def verify_uki(path):
    subprocess.run(['sbverify', '--cert', str(KEYS/'MOK.pem'), str(path)], check=True)
    sections = subprocess.check_output(['objdump', '-h', str(path)], text=True)
    if any(not re.search(r'\s'+re.escape(s)+r'\s', sections) for s in ('.linux', '.initrd', '.cmdline', '.osrel', '.sbat')):
        raise InvalidBootImage('Signed image lacks a required embedded UKI section')
    with tempfile.TemporaryDirectory(dir='/var/lib/omarchy-custom') as tmp:
        cmdline = pathlib.Path(tmp)/'cmdline'
        subprocess.run(['objcopy', '--dump-section', '.cmdline='+str(cmdline), str(path)], check=True)
        words = cmdline.read_bytes().rstrip(b'\0').decode().split()
        if 'module.sig_enforce=1' not in words or 'lockdown=integrity' not in words:
            raise InvalidBootImage('UKI does not enforce kernel/module integrity')
        if any(w.startswith(('init=', 'rdinit=', 'module.sig_enforce=0', 'lockdown=none')) for w in words):
            raise InvalidBootImage('Unsafe embedded command line')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kernel-version', required=True)
    parser.add_argument('--initialize-stock-recovery', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0 or pathlib.Path('/run/archiso').exists():
        raise InvalidBootImage('Update signing runs only on an installed system as root')
    source = subprocess.check_output(['findmnt', '-n', '-o', 'SOURCE', '/'], text=True).strip().split('[')[0]
    types = subprocess.check_output(['lsblk', '-sno', 'TYPE', source], text=True).split()
    if 'crypt' not in types:
        raise InvalidBootImage('Signing credentials require an encrypted root')
    for p in (KEYS, KEYS/'MOK.key', KEYS/'MOK.pem'):
        if p.is_symlink() or not p.exists() or p.stat().st_uid != 0 or p.stat().st_mode & 0o077:
            raise InvalidBootImage('Signing credentials have unsafe ownership or permissions')
    version = args.kernel_version
    if not re.fullmatch(r'[A-Za-z0-9_.+-]+', version):
        raise InvalidBootImage('Invalid kernel version')
    esp = pathlib.Path('/boot')
    if subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '--mountpoint', str(esp)], text=True).strip() != 'vfat':
        raise InvalidBootImage('The target-local ESP is not mounted at /boot')
    binding = pathlib.Path('/etc/omarchy-custom/storage.json')
    if binding.is_symlink() or binding.stat().st_uid != 0 or binding.stat().st_mode & 0o077:
        raise InvalidBootImage('Installed storage binding is unsafe')
    expected = json.loads(binding.read_text())
    target_path = str(pathlib.Path(expected['by_id']).resolve(strict=True))
    esp_source = subprocess.check_output(['findmnt','-n','-o','SOURCE','--mountpoint',str(esp)],text=True).strip()
    if subprocess.check_output(['blkid','-s','PARTUUID','-o','value',esp_source],text=True).strip() != expected['esp_partuuid']:
        raise InvalidBootImage('ESP partition identity changed')
    def ancestors(path):
        tree = json.loads(subprocess.check_output(['lsblk','-sJpb','-o','NAME,TYPE,MODEL,SERIAL,SIZE',path]))
        result = []
        def walk(node):
            if node['type'] == 'disk': result.append(node)
            for child in node.get('children',[]): walk(child)
        for node in tree['blockdevices']: walk(node)
        return result
    for path in (source, esp_source):
        disks = ancestors(path)
        if len(disks) != 1:
            raise InvalidBootImage('Ambiguous installed root/ESP ancestry')
        disk = disks[0]
        if (disk['name'] != target_path or (disk.get('serial') or '').strip() != expected['serial']
                or int(disk['size']) != expected['size']
                or ''.join((disk.get('model') or '').upper().split()) != ''.join(expected['model'].upper().split())):
            raise InvalidBootImage('Root or ESP does not belong to the confirmed installation disk')
    base = pathlib.Path('/var/lib/omarchy-custom')
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='signed-update-', dir=base) as tmp:
        tmp = pathlib.Path(tmp)
        cmdline = pathlib.Path('/etc/kernel/cmdline').read_text().strip()
        if any(w.startswith(('module.sig_enforce=', 'lockdown=')) for w in cmdline.split()):
            raise InvalidBootImage('Integrity flags must be managed by the signing service')
        cmdline += ' module.sig_enforce=1 lockdown=integrity'
        (tmp/'cmdline').write_text(cmdline+'\n')
        subprocess.run(['mkinitcpio', '-k', version, '-g', str(tmp/'initrd')], check=True)
        candidate = tmp/'candidate.efi'
        subprocess.run(['ukify', 'build', '--linux=/usr/lib/modules/'+version+'/vmlinuz',
                        '--initrd='+str(tmp/'initrd'), '--cmdline=@'+str(tmp/'cmdline'),
                        '--os-release=@/etc/os-release', '--sign-kernel=yes',
                        '--secureboot-private-key='+str(KEYS/'MOK.key'),
                        '--secureboot-certificate='+str(KEYS/'MOK.pem'),
                        '--output='+str(candidate)], check=True)
        result = publish(esp, candidate, verify_uki, initialize=args.initialize_stock_recovery)
        (base/'last-signed-update.json').write_text(json.dumps(result, indent=2)+'\n')
        print('Signed update published. The separate recovery image was preserved.')


if __name__ == '__main__':
    main()
