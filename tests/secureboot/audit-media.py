"""Boot the actual signed ISO as a USB and operate its physical audit UI."""
import base64
import hashlib
import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import time

assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
ROOT = pathlib.Path('work/vm'); ROOT.mkdir(parents=True,exist_ok=True)
REPORT = pathlib.Path('out/audit-media'); REPORT.mkdir(parents=True,exist_ok=True)
IMAGE = pathlib.Path('out/hardware-validation/omarchy-hardware-validation.iso').resolve()
metadata = json.load(open(IMAGE.parent/'build-metadata.json'))
subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=IMAGE.parent,check=True)
assert metadata['profile'] == 'hardware-validation' and metadata['physical_installation_enabled'] is False
cert = base64.b64decode(metadata['certificate_der_base64'],validate=True)
assert hashlib.sha256(cert).hexdigest() == metadata['certificate_sha256']
(ROOT/'owner.der').write_bytes(cert)
subprocess.run(['openssl','x509','-inform','DER','-in',str(ROOT/'owner.der'),'-out',str(ROOT/'owner.pem')],check=True)
subprocess.run(['python3','tests/qemu/create-fixtures.py'],env=dict(os.environ,SCENARIO='cdrom'),check=True)
with (ROOT/'target.raw').open('r+b') as target:
    target.truncate(1_000_204_886_016)
before = {name:hashlib.file_digest((ROOT/name).open('rb'),'sha256').hexdigest()
          for name in ('windows-system.raw','windows-data.raw')}
assert (ROOT/'target.raw').stat().st_blocks == 0
tools = pathlib.Path('work/secureboot-tools/bin/virt-fw-vars')
subprocess.run([str(tools),'--input','/usr/share/OVMF/OVMF_VARS_4M.ms.fd',
                '--output',str(ROOT/'vars.fd'),'--add-mok','dcf13531-f232-4bb9-8efc-c0c16bcf7f24',
                str(ROOT/'owner.pem'),'--secure-boot','--output-json',str(REPORT/'enrolled-firmware.json')],check=True)
if os.environ.get('AUDIT_ENROLLED_VARS'):
    # Use firmware modified through actual MokManager keyboard confirmation.
    shutil.copyfile(os.environ['AUDIT_ENROLLED_VARS'],ROOT/'vars.fd')


class QMP:
    def __init__(self,path):
        self.sock = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        deadline = time.monotonic()+30
        while True:
            try:
                self.sock.connect(str(path)); break
            except (FileNotFoundError,ConnectionRefusedError):
                if time.monotonic()>deadline: raise
                time.sleep(0.1)
        self.file = self.sock.makefile('rwb',buffering=0)
        json.loads(self.file.readline()); self.call('qmp_capabilities')

    def call(self,name,args=None):
        self.file.write((json.dumps({'execute':name,'arguments':args or {}})+'\n').encode())
        while True:
            response = json.loads(self.file.readline())
            if 'error' in response: raise RuntimeError(str(response['error']))
            if 'return' in response: return response['return']

    def key(self,name,shift=False):
        keys = ([{'type':'qcode','data':'shift'}] if shift else [])+[{'type':'qcode','data':name}]
        self.call('send-key',{'keys':keys,'hold-time':80}); time.sleep(0.12)

    def text(self,text):
        for char in text:
            if char == '\n': self.key('ret')
            elif char.isalnum(): self.key(char.lower(),char.isupper())
            else: raise RuntimeError('Unsupported acceptance key')

    def screenshot(self,name):
        self.call('screendump',{'filename':str((REPORT/name).resolve()),'format':'png'})


accel = ['-accel','kvm','-cpu','host'] if pathlib.Path('/dev/kvm').exists() else ['-accel','tcg','-cpu','max']
if pathlib.Path('/dev/kvm').exists(): subprocess.run(['sudo','chmod','a+rw','/dev/kvm'],check=True)
qmp_path = (ROOT/'audit.sock').resolve()
serial = (REPORT/'audit-serial.log').resolve()
# A writable regular-file clone models a Rufus DD stick. The release ISO is
# never opened for writing. Kernel policy, not QEMU read-only flags, protects
# the synthetic installation and Windows disks.
usb = ROOT/'audit-usb.raw'; shutil.copyfile(IMAGE,usb)
command = ['qemu-system-x86_64','-machine','q35,smm=on',*accel,'-m','12288','-smp','4',
    '-global','driver=cfi.pflash01,property=secure,value=on',
    '-drive','if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd',
    '-drive','if=pflash,format=raw,file='+str(ROOT/'vars.fd'),
    '-device','qemu-xhci','-drive','file='+str(usb)+',format=raw,if=none,id=usb',
    '-device','usb-storage,drive=usb,bootindex=1,serial=OMARCHY_AUDIT_USB',
    '-device','virtio-scsi-pci,id=scsi',
    '-drive','file='+str(ROOT/'windows-system.raw')+',format=raw,if=none,id=a',
    '-device','scsi-hd,drive=a,bus=scsi.0,serial=WINDOWS_A,vendor=Samsung,product=990 PRO 2TB',
    '-drive','file='+str(ROOT/'windows-data.raw')+',format=raw,if=none,id=b',
    '-device','scsi-hd,drive=b,bus=scsi.0,serial=WINDOWS_B,vendor=WDC,product=WDS100T2B0B',
    '-drive','file='+str(ROOT/'target.raw')+',format=raw,if=none,id=c,detect-zeroes=off,discard=ignore',
    '-device','scsi-hd,drive=c,bus=scsi.0,serial=OMARCHYTESTC,vendor=Crucial,product=CT1000BX500SSD1',
    '-display','none','-serial','file:'+str(serial),'-monitor','none','-nic','none','-no-reboot',
    '-qmp','unix:'+str(qmp_path)+',server=on,wait=off']
process = None
try:
    with (REPORT/'qemu.log').open('wb') as output:
        process = subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT)
        qmp = QMP(qmp_path)
        deadline = time.monotonic()+240
        ready = None; typed = False
        while time.monotonic()<deadline and process.poll() is None:
            text = serial.read_text(errors='replace') if serial.exists() else ''
            if 'OMARCHY_AUTHENTICATED_LIVE_ROOT_OK' in text and ready is None:
                ready = time.monotonic()+20
            if ready and time.monotonic()>=ready and not typed:
                qmp.screenshot('audit-before-input.png')
                qmp.text('3\nOMARCHYTESTC\n')
                typed = True
            match = re.search(r'OMARCHY_HARDWARE_REPORT=(\{[^\r\n]+\})[\r\n]',text)
            if match:
                receipt = json.loads(match[1])
                assert receipt['kernel_disk_write_denials'] is True
                assert receipt['firmware'] == {'SecureBoot':1,'SetupMode':0}
                assert receipt['plan']['target']['serial'] == 'OMARCHYTESTC'
                assert receipt['plan']['target']['model'] == 'CT1000BX500SSD1'
                assert len(receipt['plan']['protected']) == 2
                (REPORT/'hardware-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
                qmp.screenshot('audit-complete.png')
                qmp.call('quit'); process.wait(timeout=20)
                break
            time.sleep(0.25)
        else:
            qmp.screenshot('audit-failure.png')
            raise RuntimeError('Actual signed USB audit did not complete its inventory/serial UI')
finally:
    if process and process.poll() is None:
        process.kill(); process.wait(timeout=20)
    after = {name:hashlib.file_digest((ROOT/name).open('rb'),'sha256').hexdigest() for name in before}
    assert before == after, 'Protected Windows fixture bytes changed'
    target = (ROOT/'target.raw').stat()
    assert target.st_size == 1_000_204_886_016 and target.st_blocks == 0, 'Blank sparse target changed'
    (REPORT/'disk-verification.json').write_text(json.dumps({'protected_before':before,'protected_after':after,
        'target_bytes':target.st_size,'target_allocated_blocks':target.st_blocks},indent=2)+'\n')
(REPORT/'result.txt').write_text('Actual signed USB image, immutable live root, physical audit entry, keyboard selection and serial validation passed. All simulated SSDs unchanged.\n')
