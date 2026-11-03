"""Cloud-only small-file tests of the real Windows PowerShell downloader."""
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('packager',pathlib.Path('scripts/package-release.py'))
packager=importlib.util.module_from_spec(spec); spec.loader.exec_module(packager)


class Download(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.temp.name)
        self.source=self.root/'omarchy-test.iso'; self.source.write_bytes(bytes(range(256))*4097)
        self.assets=self.root/'assets'
        self.manifest=packager.package(self.source,self.assets,'lachthox/omarchy-secureboot-iso','v0.0.0-test',65536)
        self.output=self.root/'output'

    def tearDown(self): self.temp.cleanup()

    def run_helper(self):
        binary=shutil.which('powershell') or shutil.which('pwsh')
        assert binary, 'PowerShell required'
        return subprocess.run([binary,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',
            str(self.assets/'Get-OmarchyISO.ps1'),'-LocalAssetsDirectory',str(self.assets),'-OutputDirectory',str(self.output)],capture_output=True,text=True)

    def test_exact_reconstruction_and_idempotent_verification(self):
        result=self.run_helper(); self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((self.output/self.source.name).read_bytes(),self.source.read_bytes())
        self.assertEqual(self.run_helper().returncode,0)

    def test_corrupt_part_refused(self):
        (self.assets/self.manifest['parts'][0]['name']).write_bytes(b'corrupt')
        self.assertNotEqual(self.run_helper().returncode,0)
        self.assertFalse((self.output/self.source.name).exists())

    def test_manifest_tampering_refused(self):
        with (self.assets/'release-download.json').open('a') as f: f.write(' ')
        self.assertNotEqual(self.run_helper().returncode,0)
        self.assertFalse((self.output/self.source.name).exists())

    def test_existing_different_file_preserved(self):
        self.output.mkdir(); target=self.output/self.source.name; target.write_bytes(b'keep this')
        self.assertNotEqual(self.run_helper().returncode,0)
        self.assertEqual(target.read_bytes(),b'keep this')

    def test_full_hash_mismatch_never_publishes_partial_iso(self):
        raw=(self.assets/'release-download.json').read_bytes()
        data=json.loads(raw); data['sha256']='0'*64
        changed=(json.dumps(data,indent=2)+'\n').encode(); (self.assets/'release-download.json').write_bytes(changed)
        helper=self.assets/'Get-OmarchyISO.ps1'
        helper.write_text(helper.read_text().replace(hashlib.sha256(raw).hexdigest(),hashlib.sha256(changed).hexdigest()))
        result=self.run_helper(); self.assertNotEqual(result.returncode,0)
        self.assertIn('Reconstructed ISO checksum mismatch',result.stderr)
        self.assertFalse((self.output/self.source.name).exists())
        self.assertFalse((self.output/(self.source.name+'.partial')).exists())


if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    unittest.main()
