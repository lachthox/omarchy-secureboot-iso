#!/usr/bin/env python3
"""Exercise the shipped wizard/runner; only identities/capacity are fixtured."""
import importlib.util
import os
import pathlib
import subprocess
import sys

SOURCE = pathlib.Path('/run/omarchy-installer')
subprocess.run(['mkdir', '-p', str(SOURCE)], check=True)
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
    assert target['size'] == 48*1024**3
    return {'encrypted': os.environ.get('WIZARD_ENCRYPTED') == '1',
            'ci_interrupt': os.environ.get('WIZARD_INTERRUPT') == '1',
            'ci_probe': str(pathlib.Path(__file__).with_name('installed-boot.sh'))}

def inventory():
    acceptance()
    disks = discovery.inventory()
    for d in disks:
        d['model'] = {'WINDOWS_A': 'Samsung SSD 990 PRO', 'WINDOWS_B': 'WDS100T2B0B',
                      'OMARCHYTESTC': 'CT1000BX500SSD1'}[d['serial']]
    return disks

acceptance()
policy.TARGET_MIN_BYTES = policy.TARGET_MAX_BYTES = 48*1024**3
spec = importlib.util.spec_from_file_location('real_wizard', SOURCE/'tui/wizard.py')
wizard = importlib.util.module_from_spec(spec); spec.loader.exec_module(wizard)
target = next(d for d in inventory() if d['serial'] == 'OMARCHYTESTC')
answers = iter([target['by_id'], 'OMARCHYTESTC', 'ERASE OMARCHYTESTC', 'omarchytest',
                'Synthetic VM User', 'vm@example.invalid', 'INSTALL OMARCHYTESTC'])
wizard.main(read=lambda prompt: next(answers), secret=lambda prompt: 'VM-only-public-test-passphrase',
            discover=inventory, acceptance=acceptance)
print('ACTUAL_GUARDED_WIZARD_ACCEPTANCE_OK', flush=True)
