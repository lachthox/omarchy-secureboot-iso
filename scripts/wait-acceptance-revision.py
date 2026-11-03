"""Keep the verified ISO on its runner while awaiting a source-only correction."""
import os
import pathlib
import subprocess
import time

assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
initial = subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
branch = os.environ['GITHUB_REF_NAME']
assert branch.startswith('codex/') and not branch.startswith('-')
deadline = time.monotonic()+600
while time.monotonic() < deadline:
    subprocess.run(['git','fetch','--quiet','origin',branch],check=True)
    revision = subprocess.check_output(['git','rev-parse','FETCH_HEAD'],text=True).strip()
    if revision != initial:
        # This checkout is disposable and cloud_only was checked above. Ignored
        # ISO/cache/report paths survive; no developer worktree is touched.
        subprocess.run(['git','reset','--hard',revision],check=True)
        print('Retesting source revision '+revision+' with the SAME verified ISO',flush=True)
        break
    time.sleep(15)
else:
    raise RuntimeError('No source correction arrived within the bounded debug window')
