"""Fail-closed storage policy. Pure functions: no device access or writes."""
import hashlib
import json

TARGET_MODEL = 'CT1000BX500SSD1'
TARGET_MIN_BYTES = 900_000_000_000
TARGET_MAX_BYTES = 1_100_000_000_000
PROTECTED_MODELS = ('990 PRO', 'WDS100T2B0B')
WINDOWS_FILESYSTEMS = {'ntfs', 'ntfs3', 'bitlocker', 'BitLocker', 'exfat'}


class Refused(ValueError):
    pass


def normalize(model):
    return ''.join(model.upper().split())


def validate_inventory(disks):
    if not disks:
        raise Refused('No physical disks discovered')
    serials, identifiers, paths = set(), set(), set()
    for disk in disks:
        if not disk.get('serial') or not disk.get('by_id') or not disk.get('model'):
            raise Refused('A disk lacks a model, serial or stable by-id identity')
        if disk['serial'] in serials or disk['by_id'] in identifiers or disk['path'] in paths:
            raise Refused('Disk identities are ambiguous')
        serials.add(disk['serial']); identifiers.add(disk['by_id']); paths.add(disk['path'])
        if disk.get('probe_error'):
            raise Refused('Filesystem probe failed: '+disk['path'])


def reasons(disk):
    result = []
    if disk.get('fstype') in WINDOWS_FILESYSTEMS or disk.get('windows'):
        result.append('Whole-disk Windows/data filesystem or BitLocker detected')
    if any(normalize(x) in normalize(disk['model']) for x in PROTECTED_MODELS):
        result.append('Protected Windows hardware model')
    if disk.get('mounted') or disk.get('holders') or disk.get('removable'):
        result.append('In use, mapped, removable or installation medium')
    for part in disk.get('partitions', []):
        if part.get('fstype') in WINDOWS_FILESYSTEMS or part.get('windows'):
            result.append('Windows/data filesystem or BitLocker detected')
        if part.get('esp'):
            result.append('Existing EFI system partition requires manual review')
        if part.get('mounted') or part.get('holders'):
            result.append('Partition in use')
    return sorted(set(result))


def identity(disk):
    result = {key: disk[key] for key in ('model', 'serial', 'size', 'by_id')}
    result['partitions'] = [{k:p.get(k) for k in ('partuuid','uuid','size','fstype','esp','windows')}
                            for p in disk.get('partitions',[])]
    return result


def plan(disks, target_id, confirmation_serial, erase_data=False):
    validate_inventory(disks)
    matches = [d for d in disks if d['by_id'] == target_id]
    if len(matches) != 1:
        raise Refused('Target does not resolve to exactly one disk')
    target = matches[0]
    if normalize(target['model']) != normalize(TARGET_MODEL):
        raise Refused('Only the configured Crucial BX500 model is eligible')
    if not TARGET_MIN_BYTES <= target['size'] <= TARGET_MAX_BYTES:
        raise Refused('Unexpected target capacity')
    if target['serial'] != confirmation_serial:
        raise Refused('Typed serial does not match selected disk')
    blocked = reasons(target)
    # Explicit whole-disk erasure may include an ordinary NTFS/exFAT data
    # partition (the intended Windows E:). It never overrides Windows boot,
    # BitLocker, protected hardware, mounts, holders or identity checks.
    if erase_data and not target.get('windows') and target.get('fstype') not in ('bitlocker', 'BitLocker') and all(
            not p.get('windows') and p.get('fstype') not in ('bitlocker', 'BitLocker')
            for p in target.get('partitions', [])):
        blocked = [r for r in blocked if r not in (
            'Whole-disk Windows/data filesystem or BitLocker detected',
            'Windows/data filesystem or BitLocker detected')]
    if blocked:
        raise Refused('; '.join(blocked))
    result = {
        'schema': 1, 'target': identity(target), 'erase_existing_data': bool(erase_data),
        'protected': sorted([identity(d) for d in disks if d is not target], key=lambda d: d['by_id']),
        'partition_plan': ['GPT on target only', '1 MiB alignment', '2 GiB FAT32 ESP on target', 'Remaining space: Omarchy Btrfs root'],
        'firmware_variables': 'no writes permitted', 'gpu_unlock': False,
    }
    result['digest'] = digest(result)
    return result


def digest(value):
    return hashlib.sha256(json.dumps({k:v for k,v in value.items() if k!='digest'}, sort_keys=True).encode()).hexdigest()


def revalidate(saved, disks):
    if saved.get('digest') != digest(saved):
        raise Refused('Plan was changed after confirmation')
    current = plan(disks, saved['target']['by_id'], saved['target']['serial'], saved.get('erase_existing_data', False))
    if current != saved:
        raise Refused('Storage identity or protected-disk set changed; reconfirm the plan')
    return next(d for d in disks if d['by_id'] == saved['target']['by_id'])
