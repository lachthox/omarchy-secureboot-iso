"""VM-only acceptance of the real installed-system update/signing entry point."""
import base64
import json
import pathlib
import subprocess
import sys

assert pathlib.Path('/sys/class/dmi/id/sys_vendor').read_text().strip() in ('QEMU', 'Bochs')
assert not pathlib.Path('/run/archiso').exists()
sys.path.insert(0, '/opt/omarchy-ci-tools/secureboot')
import bootstore
import update

variables = pathlib.Path('/sys/firmware/efi/efivars')
secure = list(variables.glob('SecureBoot-*'))
setup = list(variables.glob('SetupMode-*'))
assert len(secure) == len(setup) and len(secure) <= 1
# Unprovisioned OVMF can omit both variables on the preparation boot.
# Enforcing boots are independently required to emit the integrity marker.
enabled = secure[0].read_bytes()[4] if secure else 0
if enabled:
    assert setup[0].read_bytes()[4] == 0
    assert pathlib.Path('/sys/module/module/parameters/sig_enforce').read_text().strip() in ('Y', '1')
    assert '[integrity]' in pathlib.Path('/sys/kernel/security/lockdown').read_text()
    print('INSTALLED_SECUREBOOT_1_SETUPMODE_0_INTEGRITY_ENFORCED', flush=True)
    raise SystemExit(0)

keys = pathlib.Path('/var/lib/omarchy-custom/keys')
subprocess.run(['bash', '/opt/omarchy-ci-tools/secureboot/prepare-local-keys.sh', '--generate-local-mok'], check=True)
cmdline = pathlib.Path('/etc/kernel/cmdline')
words = [word for word in cmdline.read_text().split() if word not in ('quiet', 'splash')]
words += ['console=ttyS0,115200', 'disablehooks=plymouth', 'plymouth.enable=0']
cmdline.write_text(' '.join(words)+'\n')
version = subprocess.check_output(['uname', '-r'], text=True).strip()
command = [sys.executable, '/opt/omarchy-ci-tools/secureboot/update.py', '--kernel-version', version]
subprocess.run(command + ['--initialize-stock-recovery'], check=True)
linux = pathlib.Path('/boot/EFI/Linux')
current, recovery = linux/'omarchy-current.efi', linux/'omarchy-recovery.efi'
original = bootstore.sha256(recovery)
subprocess.run(command, check=True)
assert bootstore.sha256(recovery) == original
update.verify_uki(current)
update.verify_uki(recovery)
before = (bootstore.sha256(current), bootstore.sha256(recovery))
key = keys/'MOK.key'
saved = keys/'MOK.key.saved'
key.rename(saved)
try:
    key.write_text('deliberately invalid CI signing key\n')
    key.chmod(0o600)
    failed = subprocess.run(command)
    assert failed.returncode != 0, 'Invalid signing key must stop publication'
finally:
    key.unlink()
    saved.rename(key)
assert before == (bootstore.sha256(current), bootstore.sha256(recovery))
print('ACTUAL_SIGNED_UPDATE_AND_SIGNING_FAILURE_RECOVERY_PASSED', flush=True)
boot = pathlib.Path('/boot/EFI/BOOT')
import shutil
shutil.copyfile('/opt/omarchy-ci-tools/shimx64.efi', boot/'BOOTX64.EFI')
shutil.copyfile(current, boot/'grubx64.efi')
print('OMARCHY_CI_MOK_DER='+base64.b64encode((keys/'MOK.der').read_bytes()).decode(), flush=True)
print('SIGNED_INSTALLED_IMAGES='+json.dumps({'current': before[0], 'recovery': before[1]}), flush=True)
subprocess.run(['sync'], check=True)
