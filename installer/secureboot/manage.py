#!/usr/bin/env python3
"""Install the signed boot menu and run fail-closed package update hooks."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

from bootstore import InvalidBootImage
import update

BASE = pathlib.Path('/var/lib/omarchy-custom')
KEYS = BASE/'keys'
HERE = pathlib.Path(__file__).resolve().parent
TOOLS = HERE.parent/'tools'


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def kernel():
    files = subprocess.check_output(['pacman','-Qlq','linux-omarchy'],text=True)
    matches = re.findall(r'^/usr/lib/modules/([^/]+)/pkgbase$',files,re.M)
    if len(matches) != 1:
        raise InvalidBootImage('Expected exactly one installed linux-omarchy kernel')
    return matches[0]


def require_keys():
    for p in (KEYS, KEYS/'MOK.key', KEYS/'MOK.pem', KEYS/'MOK.der'):
        if not p.exists() or p.is_symlink() or p.stat().st_uid != 0 or p.stat().st_mode & 0o077:
            raise InvalidBootImage('Local signing credentials are missing or have unsafe permissions')
    run(['openssl','pkey','-in',str(KEYS/'MOK.key'),'-check','-noout'],stdout=subprocess.DEVNULL)
    key_public = subprocess.check_output(['openssl','pkey','-in',str(KEYS/'MOK.key'),'-pubout'])
    cert_public = subprocess.check_output(['openssl','x509','-in',str(KEYS/'MOK.pem'),'-pubkey','-noout'])
    if key_public != cert_public:
        raise InvalidBootImage('Signing key and certificate do not match')


def sign_modules(version):
    """DKMS normally signs before compression; also cover existing modules."""
    modules = pathlib.Path('/usr/lib/modules')/version
    sign = modules/'build/scripts/sign-file'
    external = sorted((modules/'updates').rglob('*.ko*')) if (modules/'updates').is_dir() else []
    for module in external:
        if module.is_symlink() or not module.is_file() or module.suffix not in ('.ko','.zst','.xz'):
            raise InvalidBootImage('Unexpected external module layout')
        if not sign.is_file():
            raise InvalidBootImage('Matching kernel headers are required to sign DKMS modules')
        import tempfile
        with tempfile.TemporaryDirectory(dir=BASE) as tmp:
            unpacked = pathlib.Path(tmp)/'module.ko'
            if module.suffix == '.zst':
                data = subprocess.check_output(['zstd','-dc',str(module)])
            elif module.suffix == '.xz':
                import lzma
                data = lzma.decompress(module.read_bytes())
            else:
                data = module.read_bytes()
            magic = b'~Module signature appended~\n'
            while data.endswith(magic):
                header = data[-len(magic)-12:-len(magic)]
                size = int.from_bytes(header[-4:],'big')+header[3]+header[4]
                data = data[:-len(magic)-12-size]
            if not data.startswith(b'\x7fELF'):
                raise InvalidBootImage('External module is not a valid ELF file')
            unpacked.write_bytes(data)
            run([str(sign),'sha512',str(KEYS/'MOK.key'),str(KEYS/'MOK.der'),str(unpacked)])
            if module.suffix == '.zst':
                signed = subprocess.check_output(['zstd','-q','-c',str(unpacked)])
            elif module.suffix == '.xz':
                import lzma
                signed = lzma.compress(unpacked.read_bytes(),check=lzma.CHECK_CRC32)
            else:
                signed = unpacked.read_bytes()
            temporary = module.with_name(module.name+'.omarchy-new')
            temporary.write_bytes(signed); temporary.chmod(module.stat().st_mode & 0o777)
            os.replace(temporary,module)
    if external:
        run(['depmod',version])
    # A physical RTX 3070 must have a driver for the selected kernel. The
    # firmware/module enforcement checks still decide whether it can load.
    devices = subprocess.check_output(['lspci','-Dn'],text=True)
    if any(pci in devices for pci in ('10de:2484','10de:2488')):
        run(['modinfo','-k',version,'nvidia'],stdout=subprocess.DEVNULL)


def preserve_modules(version):
    saved = BASE/'recovery-modules'
    if saved.exists():
        raise InvalidBootImage('Existing recovery modules will not be overwritten')
    shutil.copytree(pathlib.Path('/usr/lib/modules')/version,saved,symlinks=True)
    (BASE/'recovery-kernel').write_text(version+'\n')


def restore_modules():
    version = (BASE/'recovery-kernel').read_text().strip()
    if not version or '/' in version or version.startswith('.'):
        raise InvalidBootImage('Invalid retained recovery kernel')
    target = pathlib.Path('/usr/lib/modules')/version
    owned = subprocess.run(['pacman','-Qo',str(target/'pkgbase')],capture_output=True).returncode == 0
    if not owned:
        shutil.copytree(BASE/'recovery-modules',target,symlinks=True,dirs_exist_ok=True)
        run(['depmod',version])


def refresh_manager():
    candidate = BASE/'systemd-boot.signed.efi'
    source = pathlib.Path('/usr/lib/systemd/boot/efi/systemd-bootx64.efi')
    if not source.is_file(): source = TOOLS/'systemd-bootx64.efi'
    run(['sbsign','--key',str(KEYS/'MOK.key'),'--cert',str(KEYS/'MOK.pem'),
         '--output',str(candidate),str(source)])
    run(['sbverify','--cert',str(KEYS/'MOK.pem'),str(candidate)])
    boot = pathlib.Path('/boot/EFI/BOOT'); boot.mkdir(parents=True,exist_ok=True)
    manager = boot/'grubx64.efi'
    if manager.exists():
        run(['sbverify','--cert',str(KEYS/'MOK.pem'),str(manager)])
        shutil.copyfile(manager,boot/'grubx64.previous.efi')
    staged = boot/'grubx64.efi.new'
    shutil.copyfile(candidate,staged)
    with staged.open('rb') as file: os.fsync(file.fileno())
    os.replace(staged,manager)


def signed_menu():
    refresh_manager()
    boot = pathlib.Path('/boot/EFI/BOOT')
    # First retain the signed manager and public enrollment material, then
    # select shim. These operations never register or reorder firmware entries.
    for source, name in ((TOOLS/'mmx64.efi','mmx64.efi'),
                         (KEYS/'MOK.der','omarchy-owner.cer'), (TOOLS/'shimx64.efi','BOOTX64.EFI')):
        staged = boot/(name+'.new')
        shutil.copyfile(source,staged)
        with staged.open('rb') as file:
            os.fsync(file.fileno())
        os.replace(staged,boot/name)
    loader = pathlib.Path('/boot/loader'); (loader/'entries').mkdir(parents=True,exist_ok=True)
    (loader/'loader.conf').write_text('default omarchy-current.conf\ntimeout 5\neditor no\nauto-entries no\nauto-firmware no\nconsole-mode keep\n')
    for name, title in (('current','Omarchy'),('recovery','Omarchy stock recovery')):
        (loader/'entries'/f'omarchy-{name}.conf').write_text(
            f'title {title}\nsort-key omarchy-{1 if name == "current" else 2}\nefi /EFI/Omarchy/omarchy-{name}.efi\n')
    hide_upstream_images()
    run(['sync'])


def hide_upstream_images():
    # Upstream rebuild hooks run on package upgrades too. Retain their latest
    # images outside automatic discovery on every managed update.
    upstream = pathlib.Path('/boot/.omarchy-upstream'); upstream.mkdir(exist_ok=True)
    for p in pathlib.Path('/boot/EFI/Linux').glob('omarchy_*.efi'):
        os.replace(p,upstream/p.name)


def install_hooks():
    hooks = pathlib.Path('/etc/pacman.d/hooks'); hooks.mkdir(parents=True,exist_ok=True)
    command = '/usr/bin/python /usr/local/lib/omarchy-custom/secureboot/manage.py'
    triggers = '''[Trigger]
Operation = Install
Operation = Upgrade
Operation = Remove
Type = Path
Target = usr/lib/modules/*
Target = usr/src/*/dkms.conf
Target = usr/lib/firmware/*
Target = usr/lib/initcpio/*
Target = usr/lib/systemd/boot/efi/*
Target = etc/mkinitcpio.conf*
Target = etc/modprobe.d/*
'''
    (hooks/'00-omarchy-secureboot-preflight.hook').write_text(triggers+f'''
[Action]
Description = Verify the existing signed boot and recovery images
When = PreTransaction
Exec = {command} preflight
AbortOnFail
''')
    (hooks/'zz-omarchy-secureboot-update.hook').write_text(triggers+f'''
[Action]
Description = Sign and publish Omarchy boot images; retain stock recovery
When = PostTransaction
Exec = {command} update
''')
    # Normal unsigned fallback deployment must never replace our signed shim.
    for name in ('80-limine-efi-deploy.hook','99-omarchy-limine.hook'):
        p = hooks/name
        if p.exists() or p.is_symlink(): p.unlink()
        p.symlink_to('/dev/null')
    for hook in pathlib.Path('/usr/share/libalpm/hooks').glob('*.hook'):
        if re.search(r'^Exec\s*=.*\bbootctl\s+(update|install)\b',hook.read_text(),re.M):
            override = hooks/hook.name
            if override.exists() or override.is_symlink(): override.unlink()
            override.symlink_to('/dev/null')
    defaults = pathlib.Path('/etc/default/limine')
    text = re.sub(r'^ENABLE_LIMINE_FALLBACK=.*\n?','',defaults.read_text(),flags=re.M)
    defaults.write_text(text.rstrip()+'\nENABLE_LIMINE_FALLBACK=no\n')
    units = pathlib.Path('/etc/systemd/system'); units.mkdir(exist_ok=True)
    service = units/'systemd-boot-update.service'
    if service.exists() or service.is_symlink(): service.unlink()
    service.symlink_to('/dev/null')
    dkms = pathlib.Path('/etc/dkms/framework.conf.d'); dkms.mkdir(parents=True,exist_ok=True)
    (dkms/'omarchy-secureboot.conf').write_text(
        f'mok_signing_key="{KEYS}/MOK.key"\nmok_certificate="{KEYS}/MOK.der"\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation',choices=('initialize','preflight','update'))
    args = parser.parse_args()
    if os.geteuid() != 0 or pathlib.Path('/run/archiso').exists():
        raise InvalidBootImage('Signing policy runs on the encrypted installed system as root')
    os.environ['PATH'] = str(TOOLS/'bin')+':'+os.environ.get('PATH','/usr/bin')
    if args.operation == 'initialize':
        run(['bash',str(HERE/'prepare-local-keys.sh'),'--generate-local-mok'])
    require_keys()
    current = pathlib.Path('/boot/EFI/Omarchy/omarchy-current.efi')
    recovery = current.with_name('omarchy-recovery.efi')
    if args.operation == 'preflight':
        update.verify_uki(current); update.verify_uki(recovery)
        print('OMARCHY_SIGNED_UPDATE_PREFLIGHT_OK',flush=True)
        return
    if args.operation != 'initialize':
        restore_modules()
    version = kernel()
    sign_modules(version)
    if args.operation == 'initialize':
        preserve_modules(version)
    command = [sys.executable,str(HERE/'update.py'),'--kernel-version',version]
    if args.operation == 'initialize': command += ['--initialize-stock-recovery']
    run(command)
    signed_menu() if args.operation == 'initialize' else refresh_manager()
    hide_upstream_images()
    install_hooks()
    print('OMARCHY_SIGNED_PACKAGE_POLICY_READY',flush=True)


if __name__ == '__main__':
    main()
