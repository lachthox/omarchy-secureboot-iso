#!/usr/bin/env python3
"""Start physical validation with kernel-enforced read-only block access."""
import json
import os
import pathlib

def audit_command(command, pty=True):
    return ['systemd-run', '--quiet', '--wait', '--pty' if pty else '--pipe', '--collect',
        '--unit=omarchy-hardware-validation', '--property=DevicePolicy=closed',
        '--property=DeviceAllow=block-* r', '--property=NoNewPrivileges=yes',
        '--property=ProtectControlGroups=yes', '--property=PrivateMounts=yes',
        '--property=ReadOnlyPaths=/sys', '--property=UMask=0077',
        '--property=CapabilityBoundingSet=~CAP_SYS_ADMIN CAP_SYS_RAWIO CAP_SYS_MODULE CAP_MKNOD CAP_SYS_PTRACE CAP_BPF CAP_PERFMON',
        '--property=InaccessiblePaths=/run/systemd/private /run/dbus/system_bus_socket']+command


if __name__ == '__main__':
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    caps = json.loads((ROOT/'configs/capabilities.json').read_text())
    wizard = str(pathlib.Path(__file__).with_name('wizard.py'))
    if caps['physical_installation_enabled'] and caps['secure_boot_enforced']:
        os.execv('/usr/bin/python', ['/usr/bin/python', wizard])
    else:
        os.execv('/usr/bin/systemd-run', audit_command(['/usr/bin/python', wizard, '--audit']))
