"""Download one immutable Actions artifact using parallel HTTP ranges on a runner."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args): return None


def artifact_url(repository,artifact_id):
    request=urllib.request.Request(f'https://api.github.com/repos/{repository}/actions/artifacts/{artifact_id}/zip',
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    try:
        urllib.request.build_opener(NoRedirect).open(request,timeout=30)
    except urllib.error.HTTPError as response:
        if response.code!=302: raise RuntimeError('Artifact URL request failed: HTTP '+str(response.code)) from None
        url=response.headers['Location']
        assert url.startswith('https://')
        return url
    raise RuntimeError('Artifact API did not return a download redirect')


def parallel_download(url,size,destination,workers=8):
    """Bounded memory; all range requests start before the signed URL expires."""
    workers=min(workers,size)
    with tempfile.TemporaryDirectory(dir=destination.parent,prefix='artifact-parts-') as temp:
        root=pathlib.Path(temp)
        def fetch(index):
            start=size*index//workers; end=size*(index+1)//workers-1
            request=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}'})
            with urllib.request.urlopen(request,timeout=90) as response:
                if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{size}':
                    raise RuntimeError('Artifact server did not honor an exact byte range')
                with (root/str(index)).open('xb') as out:
                    shutil.copyfileobj(response,out,1024*1024)
            assert (root/str(index)).stat().st_size==end-start+1, 'Truncated artifact range'
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(fetch,range(workers)))
        digest=hashlib.sha256()
        with destination.open('xb') as out:
            for index in range(workers):
                piece=root/str(index)
                with piece.open('rb') as src:
                    while block:=src.read(1024*1024): out.write(block); digest.update(block)
                piece.unlink()
        return digest.hexdigest()


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    p=argparse.ArgumentParser(); p.add_argument('--repository',required=True); p.add_argument('--run',required=True)
    p.add_argument('--destination',type=pathlib.Path,required=True); a=p.parse_args()
    assert re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',a.repository) and a.run.isdigit()
    response=json.loads(subprocess.check_output(['gh','api',f'repos/{a.repository}/actions/runs/{a.run}/artifacts']))
    matches=[x for x in response['artifacts'] if x['name']=='diagnostic-iso' and not x['expired']]
    assert len(matches)==1, 'Expected one immutable diagnostic-iso artifact'
    artifact=matches[0]; size=artifact['size_in_bytes']
    assert shutil.disk_usage('.').free>3*size, 'Insufficient space for artifact download/extraction'
    a.destination.mkdir(parents=True,exist_ok=True)
    assert not list(a.destination.iterdir()), 'Artifact output directory must be empty'
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='omarchy-artifact-') as temp:
        archive=pathlib.Path(temp)/'artifact.zip'
        digest=parallel_download(artifact_url(a.repository,artifact['id']),size,archive)
        expected=artifact.get('digest')
        assert expected=='sha256:'+digest, 'Actions artifact archive SHA256 mismatch or unavailable digest'
        with zipfile.ZipFile(archive) as z:
            files=[i for i in z.infolist() if not i.is_dir()]
            names={i.filename for i in files}
            assert 'SHA256SUMS' in names and 'build-metadata.json' in names
            assert len([n for n in names if n.endswith('.iso')])==1 and len(files)==3
            for entry in files:
                assert re.fullmatch(r'[A-Za-z0-9._-]+',entry.filename)
                assert (entry.external_attr>>16)&0o170000!=0o120000, 'Symlink in artifact'
                with z.open(entry) as src,(a.destination/entry.filename).open('xb') as out:
                    shutil.copyfileobj(src,out,1024*1024)
    report={'artifact_id':artifact['id'],'zip_sha256':digest,'bytes':size,'parallel_connections':8,
            'seconds':round(time.monotonic()-started,2)}
    print(json.dumps(report))
    pathlib.Path('out').mkdir(exist_ok=True)
    pathlib.Path('out/artifact-download-performance.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__': main()
