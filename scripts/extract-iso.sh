#!/usr/bin/env bash
source scripts/common.sh
cloud_only
[[ -f work/iso/arch/x86_64/airootfs.sfs ]]
python3 scripts/check-compatibility.py
sudo unsquashfs -d work/rootfs work/iso/arch/x86_64/airootfs.sfs
sudo du -B1 -s work/rootfs > out/rootfs-space.txt
