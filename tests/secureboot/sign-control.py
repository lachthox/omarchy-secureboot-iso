"""Re-sign one real live-kernel module to exercise MOK trust in the guest."""
import pathlib
import struct
import subprocess
import sys

root = pathlib.Path('work/secure-live')
listing = subprocess.check_output(['unsquashfs','-ll',str(root/'airootfs.sfs')],text=True)
paths = [line.split('squashfs-root/',1)[1] for line in listing.splitlines()
         if 'squashfs-root/usr/lib/modules/' in line and line.endswith('/drivers/net/dummy.ko.zst')]
assert len(paths) == 1, 'Ambiguous live-kernel module'
compressed = subprocess.check_output(['unsquashfs','-cat',str(root/'airootfs.sfs'),paths[0]])
data = subprocess.check_output(['zstd','-dc'],input=compressed)
magic = b'~Module signature appended~\n'
assert data.endswith(magic)
header = data[-len(magic)-12:-len(magic)]
length = int.from_bytes(header[-4:],'big')+header[3]+header[4]
unsigned = root/'unsigned-dummy.ko'
unsigned.write_bytes(data[:-len(magic)-12-length])
share = root/'module-share'; share.mkdir(exist_ok=True)
signature = subprocess.check_output(['openssl','cms','-sign','-binary','-noattr','-nosmimecap',
    '-md','sha512','-in',str(unsigned),'-signer',sys.argv[2],'-inkey',sys.argv[1],'-outform','DER'])
(share/sys.argv[3]).write_bytes(unsigned.read_bytes()+signature+bytes([0,0,2,0,0,0,0,0])+struct.pack('>I',len(signature))+magic)
