"""Report the actual live kernel's verification capabilities without changing it."""
import gzip
import pathlib
import shutil
import subprocess

try:
    config = gzip.decompress(pathlib.Path('/proc/config.gz').read_bytes()).decode()
    for line in config.splitlines():
        if any(word in line for word in ('CONFIG_MODULE_SIG', 'CONFIG_SYSTEM_TRUSTED',
                'CONFIG_SECONDARY_TRUSTED', 'CONFIG_INTEGRITY', 'CONFIG_LOCK_DOWN',
                'CONFIG_SECURITY_LOCKDOWN', 'CONFIG_EFI', 'CONFIG_IKCONFIG', 'CONFIG_DM_VERITY')):
            print('LIVE_KERNEL '+line, flush=True)
except OSError as exc:
    print('LIVE_KERNEL_CONFIG_UNAVAILABLE '+str(exc), flush=True)
for name in ('ukify', 'sbsign', 'sbverify', 'openssl', 'mokutil', 'keyctl', 'objcopy', 'lsinitcpio'):
    print('LIVE_SECURITY_TOOL '+name+'='+str(shutil.which(name)), flush=True)
for name in ('virtio_blk', 'btrfs', 'squashfs', 'nvidia', 'dm_crypt'):
    result = subprocess.run(['modinfo', '-F', 'signer', name], capture_output=True, text=True)
    print('LIVE_MODULE_SIGNER '+name+'='+result.stdout.strip(), flush=True)
for name in ('SecureBoot', 'SetupMode'):
    paths = list(pathlib.Path('/sys/firmware/efi/efivars').glob(name+'-*'))
    print('LIVE_FIRMWARE '+name+'='+str(paths[0].read_bytes()[4] if len(paths) == 1 else 'unavailable'), flush=True)

if 'module.sig_enforce=1' in pathlib.Path('/proc/cmdline').read_text().split():
    assert pathlib.Path('/sys/module/module/parameters/sig_enforce').read_text().strip() in ('Y','1')
    assert '[integrity]' in pathlib.Path('/sys/kernel/security/lockdown').read_text()
    assert not pathlib.Path('/sys/module/dummy').exists(), 'Unsigned control needs an unloaded module'
    module = subprocess.check_output(['modinfo','-n','dummy'],text=True).strip()
    if module.endswith('.zst'):
        data = subprocess.check_output(['zstd','-dc',module])
    elif module.endswith('.xz'):
        import lzma
        data = lzma.decompress(pathlib.Path(module).read_bytes())
    else:
        data = pathlib.Path(module).read_bytes()
    magic = b'~Module signature appended~\n'
    assert data.endswith(magic), 'Positive module must have an upstream signature'
    header = data[-len(magic)-12:-len(magic)]
    signature_size = int.from_bytes(header[-4:],'big')+header[3]+header[4]
    unsigned = pathlib.Path('/run/omarchy-unsigned-control.ko')
    unsigned.write_bytes(data[:-len(magic)-12-signature_size])
    result = subprocess.run(['insmod',str(unsigned)],capture_output=True,text=True)
    assert result.returncode != 0 and any(s in result.stderr.lower() for s in ('key was rejected','required key not available')), result.stderr
    unsigned.unlink()
    subprocess.run(['modprobe','dummy'],check=True)
    assert pathlib.Path('/sys/module/dummy').exists()
    print('UNSIGNED_MODULE_REJECTED_SIGNED_MODULE_ACCEPTED',flush=True)
