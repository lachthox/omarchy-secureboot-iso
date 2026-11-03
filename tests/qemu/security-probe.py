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
