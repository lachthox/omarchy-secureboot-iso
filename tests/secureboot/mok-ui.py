"""Exercise real MokManager with keyboard input; only cloud VM firmware changes."""
import hashlib
import json
import os
import pathlib
import re
import socket
import subprocess
import time

assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
ROOT=pathlib.Path('work/enrollment'); ROOT.mkdir(parents=True,exist_ok=True)
REPORT=pathlib.Path('out/enrollment'); REPORT.mkdir(parents=True,exist_ok=True)
IMAGE=pathlib.Path('out/hardware-validation/omarchy-hardware-validation.iso').resolve()
TOOLS='work/secureboot-tools/bin/virt-fw-vars'


class QMP:
    def __init__(self,path):
        self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        for _ in range(300):
            try: self.socket.connect(str(path)); break
            except (FileNotFoundError,ConnectionRefusedError): time.sleep(.1)
        else: raise RuntimeError('QMP did not start')
        self.stream=self.socket.makefile('rwb',buffering=0)
        self.stream.readline(); self.call('qmp_capabilities')

    def call(self,name,args=None):
        self.stream.write((json.dumps({'execute':name,'arguments':args or {}})+'\n').encode())
        while True:
            line=self.stream.readline()
            if not line: raise RuntimeError('QEMU disconnected')
            response=json.loads(line)
            if 'error' in response: raise RuntimeError(str(response['error']))
            if 'return' in response: return response['return']

    def key(self,name):
        self.call('send-key',{'keys':[{'type':'qcode','data':name}],'hold-time':80})
        time.sleep(.25)

    def screenshot(self,name):
        self.call('screendump',{'filename':str((REPORT/name).resolve()),'format':'png'})


def firmware(path,output):
    subprocess.run([TOOLS,'--input',str(path),'--output-json',str(output)],check=True)
    return json.loads(output.read_text())


def platform(state):
    return {v['name']:v for v in state['variables'] if v['name'] in ('PK','KEK','db','dbx')}


def test(cancel):
    name='cancel' if cancel else 'enroll'
    variables=ROOT/(name+'-vars.fd')
    subprocess.run([TOOLS,'--input','/usr/share/OVMF/OVMF_VARS_4M.ms.fd',
                    '--output',str(variables),'--secure-boot'],check=True)
    baseline=firmware(variables,REPORT/(name+'-before.json'))
    log=REPORT/(name+'-serial.log'); sock=(ROOT/(name+'.sock')).resolve()
    accel=['-accel','kvm','-cpu','host'] if pathlib.Path('/dev/kvm').exists() else ['-accel','tcg','-cpu','max']
    if pathlib.Path('/dev/kvm').exists(): subprocess.run(['sudo','chmod','a+rw','/dev/kvm'],check=True)
    command=['qemu-system-x86_64','-machine','q35,smm=on',*accel,'-m','12288','-smp','4',
        '-global','driver=cfi.pflash01,property=secure,value=on',
        '-drive','if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd',
        '-drive','if=pflash,format=raw,file='+str(variables),
        '-device','qemu-xhci','-drive','file='+str(IMAGE)+',format=raw,readonly=on,if=none,id=usb',
        '-device','usb-storage,drive=usb,bootindex=1','-display','none',
        '-serial','file:'+str(log),'-monitor','none','-nic','none','-no-reboot',
        '-qmp','unix:'+str(sock)+',server=on,wait=off']
    process=None
    def wait(token,offset=0,timeout=40):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline and process.poll() is None:
            text=log.read_text(errors='replace') if log.exists() else ''
            if token in text[offset:]: return len(text)
            time.sleep(.1)
        qmp.screenshot(name+'-failure.png')
        raise RuntimeError('MokManager did not show '+token)
    try:
        with (REPORT/(name+'-qemu.log')).open('wb') as output:
            process=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT)
            qmp=QMP(sock)
            offset=wait('Verification failed')
            qmp.screenshot(name+'-untrusted.png'); qmp.key('ret')
            wait('Press any key to perform MOK management',offset)
            qmp.key('ret'); offset=wait('Enroll key from disk',offset)
            qmp.screenshot(name+'-menu.png')
            if cancel:
                qmp.key('esc'); time.sleep(3)
            else:
                qmp.key('down'); qmp.key('ret')
                offset=wait('Select Key',offset); time.sleep(1)
                qmp.screenshot('enroll-volume.png')
                qmp.key('ret'); time.sleep(1)
                qmp.screenshot('enroll-root.png')
                # The following navigation is checked against rendered menus.
                offset=wait('EFI/',offset); qmp.key('ret')
                offset=wait('BOOT/',offset); qmp.key('down'); qmp.key('ret')
                offset=wait('omarchy-live.cer',offset)
                qmp.screenshot('enroll-files.png')
                for _ in range(4): qmp.key('down')
                qmp.key('ret'); offset=wait('View key 0',offset)
                qmp.key('ret'); offset=wait('[Fingerprint]',offset)
                qmp.screenshot('enroll-certificate.png')
                qmp.key('ret'); time.sleep(.5); qmp.key('down'); qmp.key('ret')
                offset=wait('Enroll the key(s)?',offset)
                qmp.screenshot('enroll-confirmation.png')
                qmp.key('down'); qmp.key('ret')
                offset=wait('Reboot',offset); qmp.screenshot('enroll-complete.png')
                qmp.key('ret'); process.wait(timeout=20)
            if process.poll() is None: qmp.call('quit'); process.wait(timeout=20)
    finally:
        if process and process.poll() is None: process.kill(); process.wait(timeout=20)
    after=firmware(variables,REPORT/(name+'-after.json'))
    assert platform(baseline)==platform(after), 'Platform trust databases changed'
    data=variables.read_bytes()
    import base64
    certificate=base64.b64decode(json.loads((IMAGE.parent/'build-metadata.json').read_text())['certificate_der_base64'],validate=True)
    # The exact DER must be present only after the real confirmation, not cancel.
    assert (certificate in data) is (not cancel)
    assert 'OMARCHY_AUTHENTICATED_LIVE_ROOT_OK' not in log.read_text(errors='replace')
    return variables


test(True)
variables=test(False)
(REPORT/'result.txt').write_text('Actual MokManager disk enrollment and cancellation passed; PK/KEK/db/dbx unchanged.\n')
print('ACTUAL_MOKMANAGER_ENROLLMENT_AND_CANCELLATION_PASSED',flush=True)
