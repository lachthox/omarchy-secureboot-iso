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
    subprocess.run(['modprobe','omarchy_ci_trust'],check=True)
    assert pathlib.Path('/sys/module/omarchy_ci_trust').is_dir()
    print('REAL_DKMS_OWNER_SIGNED_MODULE_LOADED_UNDER_ENFORCEMENT',flush=True)
    print('INSTALLED_SECUREBOOT_1_SETUPMODE_0_INTEGRITY_ENFORCED', flush=True)
    raise SystemExit(0)

keys = pathlib.Path('/var/lib/omarchy-custom/keys')
import shutil
product = pathlib.Path('/usr/local/lib/omarchy-custom')
product.mkdir(parents=True,exist_ok=True)
shutil.copytree('/opt/omarchy-ci-tools/secureboot',product/'secureboot')
shutil.copytree('/opt/omarchy-ci-tools',product/'tools',ignore=shutil.ignore_patterns('secureboot','installed-signed-check.py'))
cmdline = pathlib.Path('/etc/kernel/cmdline')
words = [word for word in cmdline.read_text().split() if word not in ('quiet', 'splash')]
words += ['console=ttyS0,115200', 'disablehooks=plymouth', 'plymouth.enable=0']
cmdline.write_text(' '.join(words)+'\n')
version = subprocess.check_output(['uname', '-r'], text=True).strip()
command = [sys.executable, '/opt/omarchy-ci-tools/secureboot/update.py', '--kernel-version', version]
subprocess.run([sys.executable,str(product/'secureboot/manage.py'),'initialize'],check=True)
dkms_packages = list((product/'tools/packages').glob('dkms-*.pkg.tar.zst'))
assert len(dkms_packages) == 1
subprocess.run(['pacman','-U','--noconfirm',str(dkms_packages[0])],check=True)
module = pathlib.Path('/usr/src/omarchy-ci-trust-1.0'); module.mkdir()
(module/'omarchy_ci_trust.c').write_text('''#include <linux/module.h>
static int __init trust_init(void) { return 0; }
static void __exit trust_exit(void) { }
module_init(trust_init);
module_exit(trust_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Disposable Omarchy DKMS trust acceptance fixture");
''')
(module/'Makefile').write_text('obj-m += omarchy_ci_trust.o\n')
(module/'dkms.conf').write_text('''PACKAGE_NAME="omarchy-ci-trust"
PACKAGE_VERSION="1.0"
BUILT_MODULE_NAME[0]="omarchy_ci_trust"
DEST_MODULE_LOCATION[0]="/updates/dkms"
AUTOINSTALL="yes"
MAKE[0]="make -C /lib/modules/${kernelver}/build M=${dkms_tree}/${PACKAGE_NAME}/${PACKAGE_VERSION}/build"
''')
subprocess.run(['dkms','install','-m','omarchy-ci-trust','-v','1.0','-k',version],check=True)
signer = subprocess.check_output(['modinfo','-k',version,'-F','signer','omarchy_ci_trust'],text=True).strip()
assert signer == 'Omarchy machine-local owner key',signer
print('REAL_DKMS_BUILD_AND_LOCAL_KEY_SIGNING_PASSED',flush=True)
linux = pathlib.Path('/boot/EFI/Omarchy')
current, recovery = linux/'omarchy-current.efi', linux/'omarchy-recovery.efi'
original = bootstore.sha256(recovery)
subprocess.run(command, check=True)
assert bootstore.sha256(recovery) == original
packages = list((product/'tools/packages').glob('linux-omarchy-*.pkg.tar.zst'))
assert len(packages) == 1
subprocess.run(['pacman','-U','--noconfirm',str(packages[0])],check=True)
assert bootstore.sha256(recovery) == original
print('REAL_PACMAN_KERNEL_TRANSACTION_SIGNED_HOOK_PASSED',flush=True)
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
print('OMARCHY_CI_MOK_DER='+base64.b64encode((keys/'MOK.der').read_bytes()).decode(), flush=True)
print('SIGNED_INSTALLED_IMAGES='+json.dumps({'current': before[0], 'recovery': before[1]}), flush=True)
subprocess.run(['sync'], check=True)
