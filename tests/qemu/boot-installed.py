"""Capture a synthetic guest boot and answer only its test LUKS prompt."""
import argparse
import os
import pathlib
import re
import selectors
import subprocess
import time
import json
import socket

parser = argparse.ArgumentParser()
parser.add_argument('--scenario', required=True)
parser.add_argument('--log', required=True)
parser.add_argument('--recovery', action='store_true')
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
assert args.command[0] == '--' and pathlib.Path(args.command[1]).name == 'qemu-system-x86_64'
command = args.command[1:]
qmp_path = pathlib.Path('work/vm/recovery-menu.sock').resolve()
if args.recovery:
    command += ['-qmp','unix:'+str(qmp_path)+',server=on,wait=off']
process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
deadline = time.monotonic()+(180 if args.recovery else 900 if args.scenario == 'wizard-signed' else 240)
sent = False; recent = b''; recovery_selected = False

def select_recovery():
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.connect(str(qmp_path))
        stream = sock.makefile('rwb',buffering=0)
        json.loads(stream.readline())
        def execute(name,arguments=None):
            stream.write((json.dumps({'execute':name,'arguments':arguments or {}})+'\n').encode())
            while True:
                answer = json.loads(stream.readline())
                if 'error' in answer: raise RuntimeError(str(answer['error']))
                if 'return' in answer: return answer['return']
        execute('qmp_capabilities')
        for key in ('home','down','ret'):
            execute('send-key',{'keys':[{'type':'qcode','data':key}],'hold-time':100})
            time.sleep(0.2)
try:
    with pathlib.Path(args.log).open('wb') as log:
        while True:
            if time.monotonic() > deadline:
                raise RuntimeError('Installed-system boot timed out')
            for key, _ in selector.select(0.2):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                log.write(chunk); log.flush()
                recent = (recent+chunk)[-16384:]
                if args.recovery and not recovery_selected and b'Omarchy stock recovery' in recent:
                    select_recovery(); recovery_selected = True
                if (args.scenario in ('wizard-encrypted', 'wizard-signed','wizard-finalized') and not sent
                        and re.search(rb'Enter passphrase for /dev/[A-Za-z0-9/_-]+: $', recent)):
                    # cryptsetup prints its prompt before TCSAFLUSH disables echo
                    # and discards queued input. Model a human's response delay.
                    time.sleep(0.5)
                    process.stdin.write(b'VM-only-public-test-passphrase\n'); process.stdin.flush()
                    sent = True
            if process.poll() is not None and not selector.get_map():
                break
    if process.returncode:
        raise RuntimeError('QEMU installed boot exited with '+str(process.returncode))
    if args.scenario in ('wizard-encrypted', 'wizard-signed','wizard-finalized') and not sent:
        raise RuntimeError('Encrypted boot never requested the test passphrase')
    if args.recovery and not recovery_selected:
        raise RuntimeError('The signed recovery menu was never selected')
finally:
    if process.poll() is None:
        process.kill(); process.wait(timeout=10)
