import io
import pathlib
import runpy
import types
import unittest
from unittest.mock import Mock, patch


SCRIPT = pathlib.Path(__file__).resolve().parents[2]/'tests/qemu/boot-installed.py'


class EncryptedBootInput(unittest.TestCase):
    def run_boot(self, chunks):
        events = []
        process = Mock()
        process.stdin.write.side_effect = lambda value: events.append(('write', value))
        process.poll.side_effect = [None] * len(chunks) + [0, 0]
        process.returncode = 0
        selector = Mock()
        selector.select.return_value = [(types.SimpleNamespace(fileobj=process.stdout), 1)]
        selector.get_map.return_value = {}
        log = io.BytesIO()
        log.close = lambda: None
        with patch.dict('os.environ', {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted'}), \
                patch('sys.argv', [str(SCRIPT), '--scenario', 'wizard-encrypted', '--log', 'unused',
                                   '--', 'qemu-system-x86_64']), \
                patch('subprocess.Popen', return_value=process), \
                patch('selectors.DefaultSelector', return_value=selector), \
                patch('os.read', side_effect=chunks + [b'']), \
                patch('pathlib.Path.open', return_value=log), \
                patch('time.sleep', side_effect=lambda delay: events.append(('sleep', delay))):
            runpy.run_path(str(SCRIPT), run_name='__main__')
        return events

    def test_waits_for_complete_prompt_and_terminal_setup(self):
        events = self.run_boot([
            b'A password is required to access the omarchy_root volume:\nEnter passphrase',
            b' for /dev/sdc2:',
            b' ',
            b'\nOMARCHY_INSTALLED_UEFI_BOOT_OK\n',
        ])
        self.assertEqual(events, [('sleep', 0.5), ('write', b'VM-only-public-test-passphrase\n')])

    def test_does_not_send_password_for_unrelated_passphrase_text(self):
        with self.assertRaisesRegex(RuntimeError, 'never requested'):
            self.run_boot([b'Kernel command line contains passphrase diagnostics\n'])


if __name__ == '__main__':
    unittest.main()
