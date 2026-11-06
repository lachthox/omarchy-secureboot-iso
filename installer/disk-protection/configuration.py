"""Pinned upstream schema, generated here rather than accepting arbitrary seeds."""
import uuid

MIB = 1024**2
GIB = 1024**3


def configuration(target, hostname='omarchy', encrypted=False, storage=None, defer=False):
    def quantity(value):
        return {'sector_size': {'unit': 'B', 'value': 512}, 'unit': 'B', 'value': value}

    def partition(fs, start, length, flags, mountpoint=None, btrfs=None):
        return {'btrfs': btrfs or [], 'dev_path': None, 'flags': flags, 'fs_type': fs,
                'mount_options': ['compress=zstd'] if fs == 'btrfs' else [],
                'mountpoint': mountpoint, 'obj_id': str(uuid.uuid4()),
                'size': quantity(length), 'start': quantity(start), 'status': 'create', 'type': 'primary'}

    disk = {'config_type': 'default_layout', 'device_modifications': [{
        'device': target['path'], 'wipe': True, 'partitions': [
            partition('fat32', MIB, 2*GIB, ['boot', 'esp'], '/boot'),
            partition('btrfs', 2*GIB+MIB, target['size']-2*GIB-2*MIB, [], btrfs=[
                {'mountpoint': p, 'name': n} for p, n in [('/', '@'), ('/home', '@home'),
                ('/var/log', '@log'), ('/var/cache/pacman/pkg', '@pkg')]])]}]}
    if encrypted:
        if not storage or not storage.get('luks_uuid'):
            raise ValueError('Encrypted installation requires a verified pre-opened target mapper')
        disk = {'config_type': 'pre_mounted_config', 'mountpoint': '/mnt'}
    return {
        'app_config': None, 'archinstall-language': 'English', 'auth_config': {},
        'audio_config': {'audio': 'pipewire'},
        'bootloader_config': {'bootloader': 'Limine', 'uki': False, 'removable': False},
        'custom_commands': [], 'omarchy_install': {
            'input_method': 'none', 'input_xkb_layout': '',
            'mode': 'protected' if encrypted else 'full_disk',
            'defer_provisioning': defer, 'target_mount': '/mnt',
            'boot': {'esp_mount': '/boot', 'esp_path': '/EFI/limine',
                     'efi_binary': 'limine_x64.efi', 'enable_fallback': True},
            'storage': storage or {'kernel': 'linux-omarchy'}},
        'disk_config': disk, 'hostname': hostname, 'kernels': ['linux-omarchy'],
        'network_config': {'type': 'iso'}, 'ntp': True, 'parallel_downloads': 8,
        'script': None, 'services': [], 'swap': True, 'timezone': 'Australia/Brisbane',
        'locale_config': {'kb_layout': 'us', 'sys_enc': 'UTF-8', 'sys_lang': 'en_US.UTF-8'},
        'mirror_config': {'custom_repositories': [], 'custom_servers': [
            {'url': 'https://mirror.omarchy.org/$repo/os/$arch'}],
            'mirror_regions': {}, 'optional_repositories': []},
        'packages': ['base-devel', 'git', 'omarchy-keyring', 'omarchy-settings', 'omarchy'],
        'profile_config': {'gfx_driver': None, 'greeter': None, 'profile': {}}, 'version': '3.0.9'}
