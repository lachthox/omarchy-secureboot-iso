"""Split a verified ISO on a cloud runner and generate its Windows downloader."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess


def package(source, destination, repository, tag, part_size=1_500_000_000):
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    assert re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository)
    assert re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.]+)?',tag)
    assert re.fullmatch(r'omarchy[A-Za-z0-9._-]*\.iso',source.name)
    assert 0 < part_size < 2*1024**3
    destination.mkdir(parents=True,exist_ok=True)
    parts=[]; overall=hashlib.sha256(); total=0
    with source.open('rb') as src:
        index=0
        while True:
            first=src.read(min(1024*1024,part_size))
            if not first: break
            name=source.name+f'.part-{index:03d}'
            digest=hashlib.sha256(); size=0
            with (destination/name).open('xb') as out:
                block=first
                while block:
                    out.write(block); digest.update(block); overall.update(block); size+=len(block); total+=len(block)
                    if size==part_size: break
                    block=src.read(min(1024*1024,part_size-size))
            parts.append({'name':name,'size':size,'sha256':digest.hexdigest()}); index+=1
            assert index<=999
    assert total>0
    manifest={'schema':1,'repository':repository,'tag':tag,'file':source.name,'size':total,'sha256':overall.hexdigest(),'parts':parts,
              'packager_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}
    raw=(json.dumps(manifest,indent=2)+'\n').encode()
    (destination/'release-download.json').write_bytes(raw)
    template=pathlib.Path('scripts/Get-OmarchyISO.ps1.in').read_text()
    for key,value in {'@REPOSITORY@':repository,'@TAG@':tag,'@MANIFEST_SHA256@':hashlib.sha256(raw).hexdigest()}.items():
        template=template.replace(key,value)
    (destination/'Get-OmarchyISO.ps1').write_text(template,newline='\r\n')
    (destination/'SHA256SUMS').write_text(overall.hexdigest()+'  '+source.name+'\n')
    (destination/'PART-SHA256SUMS').write_text(''.join(p['sha256']+'  '+p['name']+'\n' for p in parts))
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('source',type=pathlib.Path); p.add_argument('destination',type=pathlib.Path)
    p.add_argument('--repository',required=True); p.add_argument('--tag',required=True); a=p.parse_args()
    package(a.source,a.destination,a.repository,a.tag)
