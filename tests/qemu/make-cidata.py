"""Generate a PUBLIC, credential-free test seed for the pinned ISO schema."""
import json
import pathlib
import subprocess

root=pathlib.Path('work/vm/cidata')
root.mkdir()
# The VM installation harness resolves this sentinel from its exact synthetic
# target serial immediately before entering the restricted writer service.
disk='OMARCHY_CI_RESOLVE_BY_SERIAL'
gib=1024**3; mib=1024**2; size=48*gib
def quantity(value): return {'sector_size':{'unit':'B','value':512},'unit':'B','value':value}
def partition(fs,start,length,obj,flags,btrfs=None,mountpoint=None):
    return {'btrfs':btrfs or [],'dev_path':None,'flags':flags,'fs_type':fs,'mount_options':['compress=zstd'] if fs=='btrfs' else [],
        'mountpoint':mountpoint,'obj_id':obj,'size':quantity(length),'start':quantity(start),'status':'create','type':'primary'}
config={
    'app_config':None,'archinstall-language':'English','auth_config':{},'audio_config':{'audio':'pipewire'},
    'bootloader_config':{'bootloader':'Limine','uki':False,'removable':False},'custom_commands':[],
    'omarchy_install':{'input_method':'none','input_xkb_layout':'','mode':'full_disk','defer_provisioning':True,'target_mount':'/mnt',
        'boot':{'esp_mount':'/boot','esp_path':'/EFI/limine','efi_binary':'limine_x64.efi','enable_fallback':True},'storage':{'kernel':'linux-omarchy'}},
    'disk_config':{'config_type':'default_layout','device_modifications':[{'device':disk,'wipe':True,'partitions':[
        partition('fat32',mib,2*gib,'ea21d3f2-82bb-49cc-ab5d-6f81ae94e18d',['boot','esp'],mountpoint='/boot'),
        partition('btrfs',2*gib+mib,size-2*gib-2*mib,'8c2c2b92-1070-455d-b76a-56263bab24aa',[],
            [{'mountpoint':p,'name':n} for p,n in [('/','@'),('/home','@home'),('/var/log','@log'),('/var/cache/pacman/pkg','@pkg')]])]}]},
    'hostname':'omarchy-ci','kernels':['linux-omarchy'],'network_config':{'type':'iso'},'ntp':True,'parallel_downloads':8,
    'script':None,'services':[],'swap':True,'timezone':'Australia/Brisbane',
    'locale_config':{'kb_layout':'us','sys_enc':'UTF-8','sys_lang':'en_US.UTF-8'},
    'mirror_config':{'custom_repositories':[],'custom_servers':[{'url':'https://mirror.omarchy.org/$repo/os/$arch'}],
        'mirror_regions':{},'optional_repositories':[]},
    'packages':['base-devel','git','omarchy-keyring','omarchy-settings','omarchy'],
    'profile_config':{'gfx_driver':None,'greeter':None,'profile':{}},'version':'3.0.9'}
(root/'user_configuration.json').write_text(json.dumps(config,indent=2)+'\n')
(root/'defer-provisioning').touch()
subprocess.run(['xorriso','-as','mkisofs','-V','cidata','-J','-r','-o','work/vm/cidata.iso',str(root)],check=True)
