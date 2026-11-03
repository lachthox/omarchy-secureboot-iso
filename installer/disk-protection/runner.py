#!/usr/bin/env python3
"""Target-bound launcher shared by the real wizard and VM acceptance tests.

No arbitrary commands/seeds are accepted. The privileged parent grants exact
device numbers; the upstream writer cannot create new device-mapper mappings.
Physical installation is separately gated by the wizard's release capabilities.
"""
import errno
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import time

from configuration import configuration
from discovery import inventory
from policy import Refused, identity, revalidate

HERE = pathlib.Path(__file__).resolve()
BASE = ['systemd-run', '--quiet', '--wait', '--pipe', '--collect',
        '--property=DevicePolicy=closed', '--property=NoNewPrivileges=yes',
        '--property=ProtectControlGroups=yes', '--property=PrivatePIDs=yes', '--property=PrivateMounts=yes',
        '--property=SystemCallFilter=~bpf ptrace process_vm_readv process_vm_writev',
        '--property=CapabilityBoundingSet=~CAP_SYS_RAWIO CAP_SYS_PTRACE CAP_SYS_MODULE CAP_BPF CAP_PERFMON']


def block(path):
    s = os.stat(path)
    if not stat.S_ISBLK(s.st_mode):
        raise Refused('Not a block device: '+path)
    return f'{os.major(s.st_rdev)}:{os.minor(s.st_rdev)}'


def permissions(disks, target, extra=()):
    result = []
    for d in disks:
        for p in [d]+d.get('partitions', []):
            result += ['--property=DeviceAllow=/dev/block/'+block(p['path'])+
                       (' rw' if d['by_id'] == target['by_id'] else ' r')]
    for path in extra:
        result += ['--property=DeviceAllow='+path+' rw']
    return result


def same_storage(saved, disks):
    targets = [d for d in disks if d['by_id'] == saved['target']['by_id']]
    if len(targets) != 1:
        raise Refused('Selected target disappeared')
    target = targets[0]
    if any(target[k] != saved['target'][k] for k in ('model', 'serial', 'size', 'by_id')):
        raise Refused('Selected target identity changed')
    protected = sorted([identity(d) for d in disks if d is not target], key=lambda d: d['by_id'])
    if protected != saved['protected']:
        raise Refused('Protected disks or storage topology changed')
    return target


def efivars_snapshot():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
            pathlib.Path('/sys/firmware/efi/efivars').glob('*')
            if p.name.startswith(('Boot', 'PK-', 'KEK-', 'db-', 'dbx-', 'SecureBoot-', 'SetupMode-'))}


def validate_partitions(target):
    parts = target.get('partitions', [])
    table = json.loads(subprocess.check_output(['sfdisk', '--json', target['path']]))['partitiontable']
    entries = table['partitions']
    if table['label'] != 'gpt' or table['sectorsize'] != 512 or len(entries) != 2 or len(parts) != 2:
        raise Refused('Unexpected target partition table')
    if entries[0]['start'] != 2048 or entries[0]['size'] != 4194304 or entries[1]['start'] != 4196352:
        raise Refused('Unexpected target partition boundaries')
    paths = [e['node'] for e in entries]
    if set(paths) != {p['path'] for p in parts}:
        raise Refused('Target partition identity mismatch')
    for path in paths:
        parent = pathlib.Path('/sys/dev/block/'+block(path)).resolve().parent
        if parent != pathlib.Path('/sys/dev/block/'+block(target['path'])).resolve():
            raise Refused('Partition is not a direct descendant of the target')
    return paths


def verified_mapper(root_partition):
    mapper = pathlib.Path('/dev/mapper/omarchy_root')
    slaves = pathlib.Path('/sys/dev/block/'+block(str(mapper))).resolve()/'slaves'
    if {p.resolve() for p in slaves.iterdir()} != {
            pathlib.Path('/sys/dev/block/'+block(root_partition)).resolve()}:
        raise Refused('Encryption mapper has unexpected backing devices')
    return str(mapper)


def install(saved, account, encrypted=True, discover=inventory, ci_interrupt=False, ci_probe=None):
    if os.geteuid() != 0 or not pathlib.Path('/run/archiso').exists():
        raise Refused('Installation requires root in the booted live image')
    if subprocess.run(['mountpoint', '-q', '/mnt']).returncode == 0:
        raise Refused('/mnt is already mounted')
    from upstream import apply
    apply()  # Source compatibility must pass before the first disk write.
    disks = discover()
    target = revalidate(saved, disks)
    for d in disks:
        if d['by_id'] != target['by_id'] and any(p.get('mounted') or p.get('holders') for p in [d]+d.get('partitions', [])):
            raise Refused('A protected disk is mounted or mapped; close it before installation')
    target_number = block(target['path'])
    before_vars = efivars_snapshot()
    unit = 'omarchy-guarded-'+str(os.getpid())+'.service'
    mapper = None
    process = None
    try:
        disks = discover()
        target = revalidate(saved, disks)
        if block(target['path']) != target_number:
            raise Refused('Target kernel device changed before partitioning')
        print('GUARDED_PARTITIONING_STARTED', flush=True)
        subprocess.run(BASE+permissions(disks, target)+['sfdisk', target['path']],
                       input='label: gpt\nstart=2048,size=4194304,type=U\nstart=4196352,type=L\n', text=True, check=True)
        subprocess.run(['udevadm', 'settle'], check=True)
        disks = discover()
        target = same_storage(saved, disks)
        parts = validate_partitions(target)
        if encrypted:
            if pathlib.Path('/dev/mapper/omarchy_root').exists():
                raise Refused('An encryption mapper with the requested name already exists')
            # This small trusted stage is the ONLY process with mapper-control
            # access. No upstream installer or package scripts run in it.
            subprocess.run(BASE+permissions(disks, target, ['/dev/mapper/control'])+
                           [sys.executable, str(HERE), '--prepare-crypt', parts[1]],
                           input=account['password'].encode(), check=True)
            mapper = verified_mapper(parts[1])
        payload = {'plan': saved, 'target': target, 'parts': parts, 'account': account,
                   'mapper': mapper, 'ci_interrupt': ci_interrupt, 'ci_probe': ci_probe}
        command = BASE+['--unit='+unit]+permissions(disks, target, [mapper] if mapper else [])+[
            '--property=InaccessiblePaths=/run/systemd/private /run/dbus/system_bus_socket /dev/mapper/control',
            '--property=ReadOnlyPaths=/sys/firmware/efi/efivars',
            '--setenv=OMARCHY_PATH=/usr/share/omarchy',
            '--setenv=OMARCHY_INSTALL=/usr/share/omarchy/install',
            '--setenv=OMARCHY_UI_INTERACTIVE=no', '--setenv=OMARCHY_RUNTIME_PACKAGE=omarchy',
            '--setenv=OMARCHY_SETTINGS_PACKAGE=omarchy-settings', '--setenv=OMARCHY_NVIM_PACKAGE=omarchy-nvim',
            '--setenv=OMARCHY_MIRROR='+pathlib.Path('/root/omarchy_mirror').read_text().strip(),
            sys.executable, str(HERE), '--writer']
        process = subprocess.Popen(command, stdin=subprocess.PIPE)
        process.stdin.write(json.dumps(payload).encode()); process.stdin.close()
        deadline = time.monotonic()+1500
        while process.poll() is None:
            try:
                current = same_storage(saved, discover())
                if block(current['path']) != target_number:
                    raise Refused('Target kernel device changed during installation')
                if mapper:
                    verified_mapper(parts[1])
                if time.monotonic() > deadline:
                    raise Refused('Installation timed out')
                if ci_interrupt and pathlib.Path('/run/omarchy-guarded-interrupt-ready').exists():
                    subprocess.run(['systemctl', 'kill', '--kill-whom=all', '--signal=SIGKILL', unit], check=True)
                    if process.wait(timeout=20) == 0:
                        raise Refused('Interrupted writer unexpectedly succeeded')
                    print('GUARDED_WIZARD_INTERRUPTION_OK', flush=True)
                    break
            except BaseException:
                subprocess.run(['systemctl', 'kill', '--kill-whom=all', '--signal=SIGKILL', unit], check=False)
                process.wait(timeout=20)
                raise
            time.sleep(0.5)
        else:
            if process.returncode:
                raise Refused('Restricted upstream writer failed; retain logs and use recovery')
        if efivars_snapshot() != before_vars:
            raise Refused('Firmware boot or security variables changed')
        print('GUARDED_FIRMWARE_VARIABLES_UNCHANGED', flush=True)
    finally:
        if process is not None and process.poll() is None:
            subprocess.run(['systemctl', 'kill', '--kill-whom=all', '--signal=SIGKILL', unit], check=False)
            process.wait(timeout=20)
        # The writer has its own mount namespace; closing our verified mapper
        # after service exit cannot touch any other disk or mapping.
        if mapper:
            verified_mapper(parts[1])
            subprocess.run(['cryptsetup', 'close', 'omarchy_root'], check=True)


def denied_controls(payload):
    for d in payload['plan']['protected']:
        for p in [d]+d.get('partitions', []):
            # Resolve protected identities afresh, never trust saved /dev paths.
            if p is not d:
                continue
            disk = pathlib.Path(d['by_id']).resolve(strict=True)
            paths = [str(disk)]
            paths += [str(p) for p in pathlib.Path(d['by_id']).parent.glob(pathlib.Path(d['by_id']).name+'-part*')]
            for path in paths:
                try:
                    fd = os.open(path, os.O_WRONLY | os.O_CLOEXEC)
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EPERM):
                        raise
                else:
                    os.close(fd)
                    raise Refused('Protected disk was writable inside writer')
                with tempfile.TemporaryDirectory(dir='/run') as tmp:
                    alias = pathlib.Path(tmp)/'block-alias'
                    try:
                        os.mknod(alias, stat.S_IFBLK | 0o600, os.stat(path).st_rdev)
                        fd = os.open(alias, os.O_WRONLY | os.O_CLOEXEC)
                    except OSError as exc:
                        if exc.errno not in (errno.EACCES, errno.EPERM):
                            raise
                    else:
                        os.close(fd)
                        raise Refused('Protected alias bypassed the kernel write policy')
    print('ACTUAL_WRITER_DENIED_PROTECTED_OPENS', flush=True)


def writer():
    cgroup = pathlib.Path('/proc/self/cgroup').read_text()
    if '/omarchy-guarded-' not in cgroup or '.service' not in cgroup:
        raise Refused('Writer must run in its dedicated restricted systemd service')
    payload = json.load(sys.stdin)
    denied_controls(payload)
    target, parts, mapper = payload['target'], payload['parts'], payload['mapper']
    storage = None
    if mapper:
        verified_mapper(parts[1])
        subprocess.run(['mkfs.fat', '-F', '32', parts[0]], check=True)
        subprocess.run(['mkfs.btrfs', '-f', mapper], check=True)
        pathlib.Path('/mnt').mkdir(exist_ok=True)
        subprocess.run(['mount', mapper, '/mnt'], check=True)
        for sub in ('@', '@home', '@log', '@pkg'):
            subprocess.run(['btrfs', 'subvolume', 'create', '/mnt/'+sub], check=True)
        subprocess.run(['umount', '/mnt'], check=True)
        for sub, mount in [('@', '/mnt'), ('@home', '/mnt/home'), ('@log', '/mnt/var/log'), ('@pkg', '/mnt/var/cache/pacman/pkg')]:
            pathlib.Path(mount).mkdir(parents=True, exist_ok=True)
            subprocess.run(['mount', '-o', 'subvol='+sub+',compress=zstd', mapper, mount], check=True)
        pathlib.Path('/mnt/boot').mkdir(exist_ok=True)
        subprocess.run(['mount', parts[0], '/mnt/boot'], check=True)
        storage = {'esp_device': parts[0], 'root_device': parts[1], 'root_mapper': mapper,
                   'luks_uuid': subprocess.check_output(['cryptsetup', 'luksUUID', parts[1]], text=True).strip(),
                   'kernel': 'linux-omarchy'}
    with tempfile.TemporaryDirectory(prefix='guarded-', dir='/run') as tmp:
        root = pathlib.Path(tmp)
        config = configuration(target, encrypted=bool(mapper), storage=storage)
        account = payload['account']
        hashed = subprocess.check_output(['openssl', 'passwd', '-6', '-stdin'], input=account['password'].encode()).decode().strip()
        creds = {'root_enc_password': hashed, 'users': [{'enc_password': hashed, 'groups': [],
                 'sudo': True, 'username': account['username']}]}
        values = {'config.json': json.dumps(config), 'creds.json': json.dumps(creds),
                  'full-name': account['full_name'], 'email': account['email'], 'encrypted': str(bool(mapper)).lower()}
        for name, value in values.items():
            p = root/name; p.write_text(value); p.chmod(0o600)
        command = ['/usr/local/bin/omarchy-iso-install', '--config', str(root/'config.json'),
                   '--creds', str(root/'creds.json'), '--full-name-file', str(root/'full-name'),
                   '--email-file', str(root/'email'), '--encrypt-file', str(root/'encrypted')]
        process = subprocess.Popen(command)
        while process.poll() is None:
            if payload['ci_interrupt'] and pathlib.Path('/mnt/etc/os-release').exists():
                pathlib.Path('/run/omarchy-guarded-interrupt-ready').write_text('real target package writes\n')
                while True:
                    time.sleep(1)
            time.sleep(0.2)
        if process.returncode:
            raise Refused('Upstream installation failed')
        if not pathlib.Path('/mnt/boot/EFI/BOOT/BOOTX64.EFI').is_file() or not list(pathlib.Path('/mnt/boot/EFI/Linux').glob('*.efi')):
            raise Refused('Target-local fallback bootloader or UKI missing')
        if mapper and (pathlib.Path('/mnt/etc/omarchy/provisioning.key').exists() or
                       pathlib.Path('/mnt/var/lib/omarchy/provisioning/luks-key').exists()):
            raise Refused('An unattended unlock key was unexpectedly staged')
        state = pathlib.Path('/mnt/etc/omarchy-custom')
        state.mkdir(mode=0o700, exist_ok=True)
        binding = {k: target[k] for k in ('model','serial','size','by_id')}
        binding['esp_partuuid'] = subprocess.check_output(['blkid','-s','PARTUUID','-o','value',parts[0]],text=True).strip()
        (state/'storage.json').write_text(json.dumps(binding,indent=2)+'\n')
        (state/'storage.json').chmod(0o600)
        if payload['ci_probe']:
            # Accepted only after the harness confirms its read-only share and
            # exact VM disk identities. Never reachable in a physical session.
            import shutil
            if mapper:
                pathlib.Path('/mnt/etc/limine-entry-tool.d/98-ci-serial.conf').write_text(
                    'KERNEL_CMDLINE[default]+=" console=ttyS0,115200 disablehooks=plymouth plymouth.enable=0"\n')
                subprocess.run(['arch-chroot', '/mnt', 'limine-update'], check=True)
            probe = pathlib.Path('/mnt/usr/local/lib/omarchy-ci-installed-boot')
            probe.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(payload['ci_probe'], probe); probe.chmod(0o755)
            unit = pathlib.Path('/mnt/etc/systemd/system/omarchy-ci-installed.service')
            unit.write_text('[Unit]\nAfter=local-fs.target\nConditionVirtualization=yes\n[Service]\nType=oneshot\nExecStart=/usr/local/lib/omarchy-ci-installed-boot\n[Install]\nWantedBy=multi-user.target\n')
            wants = unit.parent/'multi-user.target.wants'; wants.mkdir(exist_ok=True)
            (wants/unit.name).symlink_to('/etc/systemd/system/'+unit.name)
        subprocess.run(['sync'], check=True)
        print('GUARDED_WIZARD_TARGET_INSTALL_OK', flush=True)


def release_target_mounts():
    if subprocess.run(['mountpoint','-q','/mnt']).returncode:
        return
    # Hibernation setup enables this target-local file globally even though
    # the installer's mounts are private. Release it before destroying the
    # namespace, so the encrypted backing device can actually be closed.
    active = [line.split()[0] for line in pathlib.Path('/proc/swaps').read_text().splitlines()[1:]]
    if '/mnt/swap/swapfile' in active:
        subprocess.run(['swapoff','/mnt/swap/swapfile'],check=True)
    # Remaining package helper processes can still have CWDs in the target.
    # systemd kills that entire cgroup when the writer exits; its private mount
    # namespace then disappears. A forced/lazy unmount here would race them.
    subprocess.run(['sync'],check=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--writer']:
        try:
            writer()
        finally:
            release_target_mounts()
    elif len(sys.argv) == 3 and sys.argv[1] == '--prepare-crypt':
        password = sys.stdin.buffer.read()
        if not password:
            raise Refused('Empty encryption passphrase')
        subprocess.run(['cryptsetup', 'luksFormat', '--type', 'luks2', '--batch-mode', '--key-file', '-', sys.argv[2]], input=password, check=True)
        subprocess.run(['cryptsetup', 'open', '--key-file', '-', sys.argv[2], 'omarchy_root'], input=password, check=True)
    else:
        raise SystemExit('This module is invoked only by the guarded wizard')
