#!/usr/bin/env python3
"""Preview-only until guarded upstream installation has passed acceptance tests."""
import importlib.util
import json
import pathlib
import sys

base = pathlib.Path(__file__).resolve().parents[1] / 'disk-protection'
sys.path.insert(0, str(base))
from discovery import inventory
from policy import Refused, plan, reasons


def main():
    print('Omarchy installation preview | Ctrl+C cancels\n')
    disks = inventory()
    for disk in disks:
        state = '; '.join(reasons(disk)) or 'Eligible for review'
        print(f"{disk['model']} | serial {disk['serial']} | {disk['size']:,} bytes\n  {disk['by_id']}\n  {state}\n")
    print('Secure Boot installation: unavailable pending verified trust-chain tests.')
    print('GPU unlock: optional post-install feature; disabled in this image.\n')
    target = input('Destination stable /dev/disk/by-id path (blank cancels): ').strip()
    if not target:
        return
    serial = input('Type the full serial printed on the destination disk: ').strip()
    proposed = plan(disks, target, serial)
    print(json.dumps(proposed, indent=2))
    print('\nPreview complete. No partitions were changed.')
    print('Installation is gated until the upstream writer and recovery tests pass.')


if __name__ == '__main__':
    try:
        main()
    except (Refused, RuntimeError, KeyboardInterrupt) as exc:
        print(f'Cancelled: {exc}', file=sys.stderr)
        raise SystemExit(1)
