"""Capture a synthetic guest boot and answer only its test LUKS prompt."""
import argparse
import os
import pathlib
import selectors
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('--scenario', required=True)
parser.add_argument('--log', required=True)
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
assert args.command[0] == '--' and pathlib.Path(args.command[1]).name == 'qemu-system-x86_64'
process = subprocess.Popen(args.command[1:], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
deadline = time.monotonic()+240
sent = False; recent = b''
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
                if args.scenario == 'wizard-encrypted' and not sent and b'passphrase' in recent.lower():
                    process.stdin.write(b'VM-only-public-test-passphrase\n'); process.stdin.flush()
                    sent = True
            if process.poll() is not None and not selector.get_map():
                break
    if process.returncode:
        raise RuntimeError('QEMU installed boot exited with '+str(process.returncode))
    if args.scenario == 'wizard-encrypted' and not sent:
        raise RuntimeError('Encrypted boot never requested the test passphrase')
finally:
    if process.poll() is None:
        process.kill(); process.wait(timeout=10)
