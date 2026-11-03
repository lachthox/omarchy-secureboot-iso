#!/usr/bin/env python3
"""Attempt real writes inside a kernel device sandbox on synthetic guest disks."""
import errno
import json
import os
import pathlib
import subprocess
import sys
import stat
import tempfile


def devices():
    vendor=pathlib.Path('/sys/class/dmi/id/sys_vendor').read_text().strip()
    assert vendor in ('QEMU','Bochs'), 'This destructive test is VM-only'
    data=json.loads(subprocess.check_output(['lsblk','-J','-p','-o','NAME,TYPE,SERIAL,RO,LABEL']))
    def source(d):
        return d.get('ro') and (d.get('label')=='OMARCHY_202610' or any(p.get('label')=='OMARCHY_202610' for p in d.get('children',[])))
    raw=[d for d in data['blockdevices'] if d['type']=='disk' and not source(d)]
    assert len(raw)==3, 'Unexpected number of synthetic disks'
    result={d.get('serial'):d for d in raw}
    assert set(result)=={'WINDOWS_A','WINDOWS_B','OMARCHYTESTC'}, 'Unexpected guest disks; refusing writes'
    return result


def child():
    disks=devices()
    for key in ('WINDOWS_A','WINDOWS_B'):
        d=disks[key]
        for path in [d['name']]+[p['name'] for p in d.get('children',[])]:
            try:
                fd=os.open(path,os.O_WRONLY|os.O_CLOEXEC)
            except OSError as exc:
                assert exc.errno in (errno.EPERM,errno.EACCES), (path,exc)
            else:
                os.close(fd)
                raise AssertionError('Protected device unexpectedly opened for writing: '+path)
            # A different path to the same kernel device must not bypass policy.
            with tempfile.TemporaryDirectory() as tmp:
                alias=str(pathlib.Path(tmp)/'alias')
                try:
                    os.mknod(alias,stat.S_IFBLK|0o600,os.stat(path).st_rdev)
                    fd=os.open(alias,os.O_WRONLY|os.O_CLOEXEC)
                except OSError as exc:
                    assert exc.errno in (errno.EPERM,errno.EACCES), exc
                else:
                    os.close(fd)
                    raise AssertionError('Protected device alias bypassed kernel policy')
    # A real target write proves the sandbox is selective rather than denying everything.
    target=disks['OMARCHYTESTC']['name']
    with open(target,'r+b',buffering=0) as f:
        f.seek(8*1024*1024); f.write(b'OMARCHY_SYNTHETIC_TARGET_WRITE\n'); os.fsync(f.fileno())
    print('KERNEL_DEVICE_WRITE_BOUNDARY_OK',flush=True)


def parent():
    probe=pathlib.Path(__file__).with_name('security-probe.py')
    if probe.exists():
        subprocess.run([sys.executable,str(probe)],check=True)
    if pathlib.Path('/dev/disk/by-label/wizard').exists():
        subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('wizard-acceptance.py'))],check=True)
        return
    disks=devices()
    command=['systemd-run','--quiet','--wait','--pipe','--collect',
        '--property=DevicePolicy=closed','--property=NoNewPrivileges=yes',
        '--property=ProtectControlGroups=yes',
        '--property=CapabilityBoundingSet=~CAP_SYS_RAWIO CAP_SYS_PTRACE CAP_SYS_MODULE CAP_BPF CAP_PERFMON',
        '--property=InaccessiblePaths=/run/systemd/private /run/dbus/system_bus_socket']
    for key,d in disks.items():
        mode='rw' if key=='OMARCHYTESTC' else 'r'
        for path in [d['name']]+[p['name'] for p in d.get('children',[])]:
            command += ['--property=DeviceAllow='+path+' '+mode]
    subprocess.run(command+[sys.executable,str(pathlib.Path(__file__).resolve()),'--child'],check=True)


if __name__=='__main__':
    child() if sys.argv[1:]==['--child'] else parent()
