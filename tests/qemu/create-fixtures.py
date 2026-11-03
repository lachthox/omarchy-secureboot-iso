"""Regular files only. No host block device, loop device, or mount access."""
import pathlib
import subprocess
import os

root = pathlib.Path('work/vm').resolve()
for name in ('windows-system.raw', 'windows-data.raw', 'target.raw'):
    p = root / name
    assert p.parent == root and not p.is_symlink()
    with p.open('xb') as f:
        f.truncate(48*1024**3 if name=='target.raw' and os.environ.get('SCENARIO') in ('install','interrupted','wizard') else 256*1024*1024)
    if name != 'target.raw':
        subprocess.run(['sgdisk', '--clear', '--new=1:2048:0', '--typecode=1:'+('ef00' if name=='windows-system.raw' else '0700'), str(p)], check=True)
    if name != 'target.raw':
        # Simulated ESP/data, explicitly not a real Windows installation.
        subprocess.run(['mkfs.fat', '--offset=2048', '-F', '32', '-n', 'WIN_ESP' if name=='windows-system.raw' else 'WIN_DATA', str(p)], check=True)
        if name == 'windows-system.raw':
            subprocess.run(['mmd', '-i', str(p)+'@@1048576', '::/EFI', '::/EFI/Microsoft', '::/EFI/Microsoft/Boot'], check=True)
            marker = root / 'BCD.fixture'
            marker.write_bytes(b'SYNTHETIC BCD - not a Windows image\n')
            subprocess.run(['mcopy', '-i', str(p)+'@@1048576', str(marker), '::/EFI/Microsoft/Boot/BCD'], check=True)
