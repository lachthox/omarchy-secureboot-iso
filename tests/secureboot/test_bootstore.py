"""Failure-atomic publication tests; firmware/signature tests are separate."""
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]/'installer/secureboot'))
import bootstore


class Publication(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.esp = self.root/'esp'; self.esp.mkdir()
        self.candidate = self.root/'candidate'
        self.candidate.write_bytes(b'verified stock image')

    def tearDown(self):
        self.tmp.cleanup()

    def verify(self, path):
        if not path.read_bytes().startswith(b'verified '):
            raise bootstore.InvalidBootImage('Signature rejected by test verifier')

    def initialize(self):
        return bootstore.publish(self.esp, self.candidate, self.verify, initialize=True)

    def test_update_preserves_recovery(self):
        original = self.initialize()
        self.candidate.write_bytes(b'verified updated image')
        updated = bootstore.publish(self.esp, self.candidate, self.verify)
        self.assertEqual(updated['recovery_sha256'], original['current_sha256'])
        self.assertNotEqual(updated['current_sha256'], original['current_sha256'])

    def test_signing_or_validation_failure_preserves_both_images(self):
        original = self.initialize()
        self.candidate.write_bytes(b'unsigned or modified image')
        with self.assertRaises(bootstore.InvalidBootImage):
            bootstore.publish(self.esp, self.candidate, self.verify)
        for name, key in (('current','current_sha256'), ('recovery','recovery_sha256')):
            self.assertEqual(bootstore.sha256(self.esp/f'EFI/Omarchy/omarchy-{name}.efi'), original[key])

    def test_interrupted_publication_preserves_active_image(self):
        original = self.initialize()
        self.candidate.write_bytes(b'verified updated image')
        with patch.object(bootstore.os, 'replace', side_effect=OSError('simulated power loss')):
            with self.assertRaises(OSError):
                bootstore.publish(self.esp, self.candidate, self.verify)
        self.assertEqual(bootstore.sha256(self.esp/'EFI/Omarchy/omarchy-current.efi'), original['current_sha256'])
        self.assertEqual(bootstore.sha256(self.esp/'EFI/Omarchy/omarchy-recovery.efi'), original['recovery_sha256'])

    def test_existing_images_cannot_be_reinitialized(self):
        self.initialize()
        with self.assertRaises(bootstore.InvalidBootImage): self.initialize()

    def test_missing_recovery_or_tampered_current_stops_update(self):
        self.initialize()
        (self.esp/'EFI/Omarchy/omarchy-recovery.efi').unlink()
        with self.assertRaises(bootstore.InvalidBootImage):
            bootstore.publish(self.esp, self.candidate, self.verify)

    def test_partial_first_publication_retains_bootable_recovery(self):
        real_replace = bootstore.os.replace
        def fail_current(src, dst):
            if pathlib.Path(dst).name == 'omarchy-current.efi': raise OSError('power lost')
            real_replace(src, dst)
        with patch.object(bootstore.os, 'replace', side_effect=fail_current):
            with self.assertRaises(OSError): self.initialize()
        self.verify(self.esp/'EFI/Omarchy/omarchy-recovery.efi')
        self.assertFalse((self.esp/'EFI/Omarchy/omarchy-current.efi').exists())


if __name__ == '__main__': unittest.main()
