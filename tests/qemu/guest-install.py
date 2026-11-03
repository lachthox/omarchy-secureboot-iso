#!/usr/bin/env python3
"""VM-only upstream unattended installation inside a device write sandbox."""
import json
import os
import pathlib
import subprocess
import sys
import shutil

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from importlib.util import spec_from_file_location, module_from_spec
spec=spec_from_file_location('guest_guard',pathlib.Path(__file__).with_name('guest-guard.py'))
guard=module_from_spec(spec); spec.loader.exec_module(guard)


def launch():
    disks=guard.devices()
    target=disks['OMARCHYTESTC']['name']
    size=int(subprocess.check_output(['blockdev','--getsize64',target]))
    assert size==48*1024**3, 'Full install needs the exact 48 GiB synthetic fixture'
    subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('offline-keyboard.py'))],check=True)
    subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('classic-chroot.py'))],check=True)
    subprocess.run(['/usr/local/bin/omarchy-cidata-load'],check=True)
    cfg=pathlib.Path('/root/user_configuration.json')
    config=json.loads(cfg.read_text())
    mods=config['disk_config']['device_modifications']
    assert len(mods)==1 and mods[0]['device']=='OMARCHY_CI_RESOLVE_BY_SERIAL'
    assert config['omarchy_install']['defer_provisioning'] and not config['custom_commands']
    mods[0]['device']=target
    cfg.write_text(json.dumps(config))
    subprocess.run(['efibootmgr','--create','--disk',disks['WINDOWS_A']['name'],'--part','1',
        '--label','Windows Boot Manager','--loader','\\EFI\\Microsoft\\Boot\\bootmgfw.efi'],check=True)
    windows_before=[line for line in subprocess.check_output(['efibootmgr','-v'],text=True).splitlines() if 'Windows Boot Manager' in line]
    assert len(windows_before)==1
    # Allocate the two expected partition device numbers inside a stage that
    # can write ONLY the verified synthetic target. No protected partition is
    # writable. Then allow only these descendants for the upstream phase.
    base=['systemd-run','--quiet','--wait','--pipe','--collect','--property=DevicePolicy=closed',
        '--property=NoNewPrivileges=yes','--property=ProtectControlGroups=yes','--property=PrivatePIDs=yes',
        '--property=SystemCallFilter=~bpf ptrace process_vm_readv process_vm_writev',
        '--property=CapabilityBoundingSet=~CAP_SYS_RAWIO CAP_SYS_PTRACE CAP_SYS_MODULE CAP_BPF CAP_PERFMON']
    subprocess.run(base+['--property=DeviceAllow='+target+' rw','sfdisk',target],
        input='label: gpt\nstart=2048,size=4194304,type=U\nstart=4196352,type=L\n',text=True,check=True)
    subprocess.run(['udevadm','settle'],check=True)
    fresh=guard.devices()
    assert fresh['OMARCHYTESTC']['name']==target
    parts=fresh['OMARCHYTESTC'].get('children',[])
    assert len(parts)==2
    command=list(base)
    for serial,d in fresh.items():
        mode='rw' if serial=='OMARCHYTESTC' else 'r'
        for path in [d['name']]+[p['name'] for p in d.get('children',[])]:
            command+=['--property=DeviceAllow='+path+' '+mode]
    command+=['--property=InaccessiblePaths=/run/systemd/private /run/dbus/system_bus_socket',
        '--setenv=OMARCHY_PATH=/usr/share/omarchy',
        '--setenv=OMARCHY_INSTALL=/usr/share/omarchy/install',
        '--setenv=OMARCHY_UI_INTERACTIVE=no',
        '--setenv=OMARCHY_RUNTIME_PACKAGE=omarchy',
        '--setenv=OMARCHY_SETTINGS_PACKAGE=omarchy-settings',
        '--setenv=OMARCHY_NVIM_PACKAGE=omarchy-nvim',
        '--setenv=OMARCHY_MIRROR='+pathlib.Path('/root/omarchy_mirror').read_text().strip(),
        '/usr/bin/python',str(pathlib.Path(__file__).resolve()),'--install-child']
    subprocess.run(command,check=True)
    windows_after=[line for line in subprocess.check_output(['efibootmgr','-v'],text=True).splitlines() if 'Windows Boot Manager' in line]
    assert windows_after==windows_before, 'Synthetic Windows EFI boot entry changed'
    print('WINDOWS_NVRAM_ENTRY_PRESERVED',flush=True)
    print('GUARDED_UPSTREAM_INSTALL_OK',flush=True)


def child():
    guard.child() # verifies real denied writes in the same cgroup as the installer
    subprocess.run(['/usr/local/bin/omarchy-iso-install','--config','/root/user_configuration.json',
        '--creds','/root/user_credentials.json','--defer-provisioning-file','/root/defer-provisioning'],check=True)
    assert pathlib.Path('/mnt/boot/EFI/limine/limine_x64.efi').is_file()
    assert list(pathlib.Path('/mnt/boot/EFI/Linux').glob('*.efi'))
    # The installed-system probe is injected only into the synthetic target,
    # after upstream installation. It is not part of the public live root.
    target=pathlib.Path('/mnt')
    probe=target/'usr/local/lib/omarchy-ci-installed-boot'
    probe.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(pathlib.Path(__file__).with_name('installed-boot.sh'),probe)
    probe.chmod(0o755)
    unit=target/'etc/systemd/system/omarchy-ci-installed.service'
    unit.write_text('[Unit]\nDescription=CI installed-system boot probe\nAfter=local-fs.target\nConditionVirtualization=qemu\n[Service]\nType=oneshot\nExecStart=/usr/local/lib/omarchy-ci-installed-boot\n[Install]\nWantedBy=multi-user.target\n')
    wants=unit.parent/'multi-user.target.wants'; wants.mkdir(exist_ok=True)
    (wants/unit.name).symlink_to('/etc/systemd/system/'+unit.name)
    print('INSTALLED_TARGET_ESP_AND_UKI_PRESENT',flush=True)


if __name__=='__main__':
    child() if sys.argv[1:]==['--install-child'] else launch()
