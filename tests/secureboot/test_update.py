import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]/'installer/secureboot'))
import update


class Verification(unittest.TestCase):
    def test_command_line_inspection_never_rewrites_signed_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            image = root/'signed.efi'
            image.write_bytes(b'signed image bytes')
            real_temporary_directory = tempfile.TemporaryDirectory

            def temporary_directory(**kwargs):
                return real_temporary_directory(dir=root)

            def run(command, **kwargs):
                if command[0] == 'objcopy':
                    self.assertEqual(command[-2], str(image))
                    self.assertNotEqual(command[-1], str(image))
                    self.assertEqual(len(command), 5)
                    pathlib.Path(command[2].split('=', 1)[1]).write_bytes(
                        b'root=/dev/mapper/root module.sig_enforce=1 lockdown=integrity\0')

            with patch.object(update.tempfile, 'TemporaryDirectory', side_effect=temporary_directory), \
                    patch.object(update.subprocess, 'run', side_effect=run), \
                    patch.object(update.subprocess, 'check_output',
                                 return_value=' .linux \n .initrd \n .cmdline \n .osrel \n .sbat \n'):
                update.verify_uki(image)
            self.assertEqual(image.read_bytes(), b'signed image bytes')


if __name__ == '__main__':
    unittest.main()
