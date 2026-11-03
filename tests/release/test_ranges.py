import importlib.util
import http.server
import os
import pathlib
import tempfile
import threading
import unittest
import hashlib

spec=importlib.util.spec_from_file_location('download',pathlib.Path('scripts/download-artifact.py'))
download=importlib.util.module_from_spec(spec); spec.loader.exec_module(download)
payload=bytes(range(256))*4097


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        bounds=self.headers['Range'].split('=',1)[1]; start,end=map(int,bounds.split('-'))
        self.send_response(206); self.send_header('Content-Range',f'bytes {start}-{end}/{len(payload)}'); self.end_headers()
        self.wfile.write(payload[start:end+1])


class Ranges(unittest.TestCase):
    def test_parallel_ranges_reconstruct_exact_bytes_and_digest(self):
        assert os.environ.get('GITHUB_ACTIONS')=='true'
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                p=pathlib.Path(tmp)/'artifact.zip'
                digest=download.parallel_download(f'http://127.0.0.1:{server.server_port}/artifact',len(payload),p)
                self.assertEqual(p.read_bytes(),payload)
                self.assertEqual(digest,hashlib.sha256(payload).hexdigest())
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__=='__main__': unittest.main()
