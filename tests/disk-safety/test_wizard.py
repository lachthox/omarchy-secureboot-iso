import contextlib
import importlib.util
import io
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_policy import fixture

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('wizard', ROOT/'installer/tui/wizard.py')
wizard = importlib.util.module_from_spec(spec); spec.loader.exec_module(wizard)
from policy import Refused
from configuration import configuration


class WizardSafety(unittest.TestCase):
    def invoke(self, answers, **options):
        with contextlib.redirect_stdout(io.StringIO()), patch.object(wizard, 'install') as install:
            wizard.main(read=lambda prompt: next(answers), secret=lambda prompt: self.fail('Unexpected secret prompt'),
                        discover=fixture, **options)
            install.assert_not_called()

    def test_blank_selection_cancels(self):
        self.invoke(iter(['']))

    def test_hardware_audit_never_requests_erasure_or_secrets(self):
        self.invoke(iter(['/dev/disk/by-id/wwn-c','LINUX-C']),audit=True)

    def test_mismatched_erasure_refuses(self):
        with self.assertRaises(Refused):
            self.invoke(iter(['/dev/disk/by-id/wwn-c','LINUX-C','yes']))

    def test_protected_hardware_remains_protected(self):
        for disk in fixture()[:2]:
            with self.assertRaises(Refused):
                self.invoke(iter([disk['by_id'],disk['serial'],'ERASE '+disk['serial']]))

    def test_unready_release_never_prompts_for_password_or_installs(self):
        self.invoke(iter(['/dev/disk/by-id/wwn-c','LINUX-C','ERASE LINUX-C']))

    def test_configuration_cannot_enable_custom_commands_or_other_disks(self):
        config=configuration(fixture()[2])
        self.assertEqual(config['custom_commands'],[])
        self.assertEqual(len(config['disk_config']['device_modifications']),1)
        self.assertEqual(config['disk_config']['device_modifications'][0]['device'],'/dev/sdb')
        self.assertFalse(config['omarchy_install']['defer_provisioning'])

    def test_install_requires_firmware_shim_and_kernel_enforcement(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            variables=root/'firmware/efi/efivars'; variables.mkdir(parents=True)
            for name,value in [('SecureBoot',1),('SetupMode',0)]:
                (variables/(name+'-test')).write_bytes(bytes([7,0,0,0,value]))
            module=root/'module/module/parameters/sig_enforce'; module.parent.mkdir(parents=True)
            module.write_text('Y\n')
            lockdown=root/'kernel/security/lockdown'; lockdown.parent.mkdir(parents=True)
            lockdown.write_text('none [integrity] confidentiality\n')
            wizard.require_enforcing_boot(root)
            for path,bad in [(variables/'SecureBoot-test',bytes([7,0,0,0,0])),
                             (variables/'SetupMode-test',bytes([7,0,0,0,1])),
                             (module,b'N\n'),(lockdown,b'[none] integrity confidentiality\n')]:
                saved=path.read_bytes(); path.write_bytes(bad)
                with self.assertRaises(Refused): wizard.require_enforcing_boot(root)
                path.write_bytes(saved)
            (variables/'MokSBStateRT-test').write_bytes(bytes([7,0,0,0,1]))
            with self.assertRaises(Refused): wizard.require_enforcing_boot(root)

    def test_encrypted_config_requires_verified_storage(self):
        with self.assertRaises(ValueError): configuration(fixture()[2],encrypted=True)


if __name__=='__main__': unittest.main()
