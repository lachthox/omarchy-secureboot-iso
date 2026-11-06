"""Read-only live Linux discovery. Never imported by local development tests."""
import json
import os
import pathlib
import subprocess


def installation_medium(disk, uuid):
    """Match the boot ISO's filesystem identity, including writable DD USBs."""
    return bool(uuid) and any(n.get('uuid') == uuid and n.get('fstype') == 'iso9660'
                              and n.get('label') == 'OMARCHY_202610'
                              for n in [disk]+disk.get('children', []))


def inventory():
    if os.name != 'posix' or not pathlib.Path('/run/archiso').exists():
        raise RuntimeError('Discovery runs only in a booted ArchISO live environment')
    data = json.loads(subprocess.check_output(['lsblk', '--json', '--bytes', '--paths', '--output',
        'NAME,TYPE,MODEL,SERIAL,SIZE,FSTYPE,PARTTYPE,PARTUUID,UUID,MOUNTPOINTS,RM,MAJ:MIN,RO,LABEL']))
    source_uuid = next((v.split('=',1)[1] for v in pathlib.Path('/proc/cmdline').read_text().split()
                        if v.startswith('archisosearchuuid=')), '')
    aliases = {}
    for p in sorted(pathlib.Path('/dev/disk/by-id').glob('*')):
        if '-part' not in p.name and p.is_symlink():
            aliases.setdefault(str(p.resolve()), []).append(str(p))
    disks = []
    for d in data['blockdevices']:
        if d['type'] != 'disk':
            continue
        if installation_medium(d, source_uuid):
            continue
        if d.get('ro') and (d.get('label') == 'OMARCHY_202610' or any(
                p.get('label') == 'OMARCHY_202610' for p in d.get('children', []))):
            continue
        path = d['name']
        ids = aliases.get(path, [])
        stable = next((i for i in ids if '/wwn-' in i), ids[0] if ids else '')
        children = d.get('children', [])
        disk = {'path':path, 'model':(d.get('model') or '').strip(), 'serial':(d.get('serial') or '').strip(),
            'size':int(d['size']), 'by_id':stable, 'major_minor':d['maj:min'], 'removable':bool(d['rm']),
            'mounted':bool(any(d.get('mountpoints') or [])), 'holders':_holders(path), 'partitions':[], 'fstype':d.get('fstype') or ''}
        for p in children:
            part = {'path':p['name'], 'major_minor':p.get('maj:min'), 'fstype':p.get('fstype') or '',
                'partuuid':p.get('partuuid'), 'uuid':p.get('uuid'), 'size':p.get('size'),
                'esp':str(p.get('parttype')).lower()=='c12a7328-f81f-11d2-ba4b-00a0c93ec93b',
                'mounted':bool(any(p.get('mountpoints') or [])), 'holders':_holders(p['name']), 'windows':False}
            # Recognize BitLocker independently of blkid's filesystem label.
            try:
                with open(p['name'], 'rb', buffering=0) as f:
                    head=f.read(512)
                if head[3:11] == b'-FVE-FS-':
                    part['fstype']='BitLocker'; part['windows']=True
                if part['esp'] and part['fstype'] in ('vfat','fat','fat32'):
                    result=subprocess.run(['mdir','-i',p['name'],'::/EFI/Microsoft/Boot'], capture_output=True)
                    part['windows']=result.returncode==0
            except OSError:
                disk['probe_error']=True
            disk['partitions'].append(part)
        disks.append(disk)
    return disks


def _holders(path):
    return bool(list((pathlib.Path('/sys/class/block')/pathlib.Path(path).name/'holders').glob('*')))
