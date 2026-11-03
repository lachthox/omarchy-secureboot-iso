import contextlib
import importlib.util
import io
import pathlib
import sys
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

    def test_encrypted_config_requires_verified_storage(self):
        with self.assertRaises(ValueError): configuration(fixture()[2],encrypted=True)


if __name__=='__main__': unittest.main()
