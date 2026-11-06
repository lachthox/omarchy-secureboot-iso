"""Extract authenticated upstream packages for real offline pacman transactions."""
import os
import pathlib
import subprocess

assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
image = pathlib.Path('out/image/omarchy-custom-diagnostic.iso')
subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=image.parent,check=True)
sfs = pathlib.Path('work/update-fixtures.sfs')
subprocess.run(['xorriso','-osirrox','on','-indev',str(image),'-extract','/arch/x86_64/airootfs.sfs',str(sfs)],check=True)
try:
    listing = subprocess.check_output(['unsquashfs','-ll',str(sfs)],text=True)
    paths = [line.split('squashfs-root/',1)[1] for line in listing.splitlines()
             if 'squashfs-root/var/cache/omarchy/mirror/offline/' in line]
    dest = pathlib.Path('work/installed-tools/packages'); dest.mkdir(exist_ok=True)
    for prefix in ('linux-omarchy-','dkms-'):
        packages = [p for p in paths if pathlib.PurePosixPath(p).name.startswith(prefix)
                    and p.endswith('.pkg.tar.zst') and '-headers-' not in p]
        assert len(packages) == 1, 'Ambiguous bundled update fixture: '+prefix
        for path in (packages[0],packages[0]+'.sig'):
            assert path in paths, 'Missing bundled package signature'
            with (dest/pathlib.PurePosixPath(path).name).open('xb') as out:
                subprocess.run(['unsquashfs','-cat',str(sfs),path],stdout=out,check=True)
finally:
    sfs.unlink()
