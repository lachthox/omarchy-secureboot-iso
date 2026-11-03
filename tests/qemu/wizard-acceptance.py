#!/usr/bin/env python3
"""Exercise the shipped wizard/runner; only identities/capacity are fixtured."""
import importlib.util
import os
import pathlib
import subprocess
import sys
import errno

SOURCE = pathlib.Path('/run/omarchy-installer')
subprocess.run(['mkdir', '-p', str(SOURCE)], check=True)
if not (SOURCE/'tui/wizard.py').exists():
    subprocess.run(['mount', '-t', '9p', '-o', 'trans=virtio,version=9p2000.L,ro,nodev,nosuid',
                    'omarchy-installer', str(SOURCE)], check=True)
sys.path.insert(0, str(SOURCE/'disk-protection'))
import discovery
import policy

def acceptance():
    assert pathlib.Path('/sys/class/dmi/id/sys_vendor').read_text().strip() in ('QEMU', 'Bochs')
    assert 'omarchy_ci=1' in pathlib.Path('/proc/cmdline').read_text().split()
    disks = discovery.inventory()
    assert {d['serial'] for d in disks} == {'WINDOWS_A', 'WINDOWS_B', 'OMARCHYTESTC'}
    target = next(d for d in disks if d['serial'] == 'OMARCHYTESTC')
    assert target['size'] == (256*1024**2 if pathlib.Path('/dev/disk/by-label/wizard-audit').exists() else 48*1024**3)
    signed = pathlib.Path('/dev/disk/by-label/wizard-signed').exists()
    return {'encrypted': signed or pathlib.Path('/dev/disk/by-label/wizard-encrypted').exists(),
            'ci_interrupt': pathlib.Path('/dev/disk/by-label/wizard-interrupted').exists(),
            'ci_probe': str(pathlib.Path(__file__).with_name('installed-signed-boot.sh' if signed else 'installed-boot.sh'))}

def inventory():
    acceptance()
    disks = discovery.inventory()
    for d in disks:
        expected = {'WINDOWS_A': '990 PRO 2TB', 'WINDOWS_B': 'WDS100T2B0B', 'OMARCHYTESTC': 'CT1000BX500SSD1'}[d['serial']]
        assert policy.normalize(d['model']) == policy.normalize(expected), (d['serial'],d['model'])
    return disks

acceptance()
audit = pathlib.Path('/dev/disk/by-label/wizard-audit').exists()
policy.TARGET_MIN_BYTES = policy.TARGET_MAX_BYTES = 256*1024**2 if audit else 48*1024**3
spec = importlib.util.spec_from_file_location('real_wizard', SOURCE/'tui/wizard.py')
wizard = importlib.util.module_from_spec(spec); spec.loader.exec_module(wizard)
target = next(d for d in inventory() if d['serial'] == 'OMARCHYTESTC')
if audit:
    if sys.argv[1:] != ['--audit-child']:
        spec = importlib.util.spec_from_file_location('real_launcher',SOURCE/'tui/launch.py')
        launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)
        subprocess.run(launcher.audit_command([sys.executable,str(pathlib.Path(__file__).resolve()),'--audit-child'],pty=False),check=True)
        raise SystemExit(0)
    for disk in inventory():
        for node in [disk]+disk.get('partitions',[]):
            try:
                fd = os.open(node['path'],os.O_WRONLY)
            except OSError as exc:
                assert exc.errno in (errno.EACCES,errno.EPERM)
            else:
                os.close(fd); raise AssertionError('Audit could open a disk for writing')
    print('AUDIT_KERNEL_DENIED_ALL_DISK_WRITES',flush=True)
    answers = iter([target['by_id'],'OMARCHYTESTC'])
    wizard.main(read=lambda prompt: next(answers),secret=lambda _: (_ for _ in ()).throw(AssertionError('Audit requested a secret')),
                discover=inventory,audit=True)
    raise SystemExit(0)
answers = iter([target['by_id'], 'OMARCHYTESTC', 'ERASE OMARCHYTESTC', 'omarchytest',
                'Synthetic VM User', 'vm@example.invalid', 'INSTALL OMARCHYTESTC'])
wizard.main(read=lambda prompt: next(answers), secret=lambda prompt: 'VM-only-public-test-passphrase',
            discover=inventory, acceptance=acceptance)
print('ACTUAL_GUARDED_WIZARD_ACCEPTANCE_OK', flush=True)
