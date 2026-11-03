#!/usr/bin/env python3
"""Run on target GPU after installation; writes measurements, never changes GPU settings."""
import argparse
import json
import pathlib
import subprocess
import time

p=argparse.ArgumentParser()
p.add_argument('--label',choices=['stock','unlocked'],required=True)
p.add_argument('--output',type=pathlib.Path,required=True)
a=p.parse_args()
import torch

assert torch.cuda.is_available(), 'A CUDA PyTorch environment is required'
assert not a.output.exists(), 'Choose a new result path; preserve previous measurements'
cmdline=pathlib.Path('/proc/cmdline').read_text()
if a.label=='stock': assert 'gpu_unlock.targets=' not in cmdline, 'Stock run must not opt into unlock'
if a.label=='unlocked': assert 'gpu_unlock.targets=' in cmdline, 'Unlocked run must opt in explicitly'
torch.backends.cuda.matmul.allow_tf32=False
torch.backends.cuda.matmul.allow_fp16_reduced_precision_reduction=False
torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction=False
def smi():
    return subprocess.check_output(['nvidia-smi','--query-gpu=name,pci.bus_id,driver_version,temperature.gpu,power.draw,power.limit,clocks.sm,pstate','--format=csv,noheader'],text=True).strip()
result={'label':a.label,'utc_epoch':time.time(),'torch':torch.__version__,'cuda':torch.version.cuda,
        'device':torch.cuda.get_device_name(0),'before':smi(),'kernel_cmdline':cmdline,'measurements':[]}
for dtype in (torch.float16,torch.bfloat16):
    n=4096
    x=torch.randn(n,n,device='cuda',dtype=dtype); y=torch.randn_like(x)
    for _ in range(20): torch.mm(x,y)
    torch.cuda.synchronize()
    for sample in range(5):
        start=torch.cuda.Event(enable_timing=True); end=torch.cuda.Event(enable_timing=True)
        start.record()
        for _ in range(100): z=torch.mm(x,y)
        end.record(); end.synchronize()
        seconds=start.elapsed_time(end)/1000
        result['measurements'].append({'dtype':str(dtype),'sample':sample,'seconds':seconds,
            'tflops':2*n**3*100/seconds/1e12,'telemetry':smi()})
result['after']=smi()
a.output.write_text(json.dumps(result,indent=2)+'\n')
print(a.output)
