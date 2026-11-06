#!/usr/bin/env python3
"""Guarded setup and read-only hardware validation for the modified official ISO."""
import getpass
import errno
import json
import os
import pathlib
import re
import subprocess
import sys

BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE/'disk-protection'))
from discovery import inventory
from policy import Refused, plan, reasons, revalidate
from runner import install


def main(read=input, secret=getpass.getpass, discover=inventory, acceptance=None, audit=False):
    print('Omarchy guarded setup | Ctrl+C cancels\n', flush=True)
    disks = discover()
    for index, d in enumerate(disks,1):
        state = '; '.join(reasons(d)) or 'Available for review'
        print(f"{index}. {d['model']} | serial {d['serial']} | {d['size']:,} bytes\n  {d['by_id']}\n  {state}", flush=True)
    print('\nThe Samsung and WD are protected. Every other unselected disk is also protected.')
    print('GPU unlock stays disabled. Secure Boot requires a separately validated signed chain.')
    target = read('Destination number or stable /dev/disk/by-id path (blank cancels): ').strip()
    if not target:
        print('Cancelled before any disk changes.')
        return
    if target.isdigit():
        number = int(target)
        if not 1 <= number <= len(disks):
            raise Refused('Destination number is outside the inventory')
        target = disks[number-1]['by_id']
    serial = read('Type the complete serial of the Crucial destination: ').strip()
    if audit:
        # Planning is pure. Explicitly preview erasure of an ordinary target
        # data filesystem without asking for permission to perform any writes.
        proposed = plan(disks, target, serial, erase_data=True)
        print(json.dumps(proposed, indent=2), flush=True)
        if os.name == 'posix' and pathlib.Path('/run/archiso').exists():
            for d in disks:
                for node in [d]+d.get('partitions',[]):
                    try:
                        fd = os.open(node['path'],os.O_WRONLY | os.O_CLOEXEC)
                    except OSError as exc:
                        if exc.errno not in (errno.EPERM,errno.EACCES):
                            raise Refused('Unable to verify audit write restrictions') from exc
                    else:
                        os.close(fd)
                        raise Refused('Audit session lacks kernel-enforced disk write restrictions')
            firmware = {}
            for name in ('SecureBoot','SetupMode'):
                files = list(pathlib.Path('/sys/firmware/efi/efivars').glob(name+'-*'))
                firmware[name] = files[0].read_bytes()[4] if len(files)==1 else None
            report = {'schema':1,'mode':'read-only','kernel_disk_write_denials':True,
                      'firmware':firmware,'plan':proposed}
            pathlib.Path('/run/omarchy-hardware-validation.json').write_text(json.dumps(report,indent=2)+'\n')
            subprocess.run(['logger','-t','omarchy-hardware-validation',
                            'OMARCHY_HARDWARE_REPORT='+json.dumps(report,separators=(',',':'))],check=True)
        print('READ_ONLY_HARDWARE_VALIDATION_COMPLETE: no installation was started.', flush=True)
        return
    erase = read('To erase ALL data and partitions on that SSD, type ERASE '+serial+': ').strip()
    if erase != 'ERASE '+serial:
        raise Refused('Whole-disk erasure was not confirmed')
    proposed = plan(disks, target, serial, erase_data=True)
    print(json.dumps(proposed, indent=2), flush=True)
    if acceptance is None:
        capabilities = json.loads((BASE.parent/'configs/capabilities.json').read_text())
        if not capabilities['physical_installation_enabled'] or not capabilities['secure_boot_enforced']:
            print('HARDWARE_VALIDATION_ONLY: '+capabilities['reason'])
            print('Disk identities and the proposed plan were checked. No partitions were changed.')
            return
    else:
        acceptance()
    username = read('New username: ').strip()
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,30}', username):
        raise Refused('Invalid username')
    full_name = read('Full name: ').strip()
    email = read('Email address: ').strip()
    password = secret('Account and disk-encryption passphrase: ')
    if len(password) < 12 or password != secret('Repeat passphrase: '):
        raise Refused('Passphrases must match and contain at least 12 characters')
    if read('Final confirmation: type INSTALL '+serial+': ').strip() != 'INSTALL '+serial:
        raise Refused('Final installation confirmation did not match')
    revalidate(proposed, discover())
    print('Starting restricted installation. Only the confirmed SSD may be written.', flush=True)
    options = acceptance() if acceptance else {}
    install(proposed, {'username': username, 'full_name': full_name, 'email': email, 'password': password},
            discover=discover, **(options or {}))
    print('Guarded installation and target boot-file checks completed.', flush=True)


if __name__ == '__main__':
    try:
        if sys.argv[1:] not in ([], ['--audit']):
            raise Refused('Unknown setup option')
        main(audit=sys.argv[1:] == ['--audit'])
    except (Refused, RuntimeError, KeyboardInterrupt, EOFError) as exc:
        print(f'Stopped: {exc}', file=sys.stderr)
        raise SystemExit(1)
