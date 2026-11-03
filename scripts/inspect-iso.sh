#!/usr/bin/env bash
source scripts/common.sh
cloud_only
iso=work/source/upstream.iso
mkdir -p out/inspection work/iso
xorriso -indev "$iso" -report_el_torito plain -report_system_area plain > out/inspection/boot-structures.txt 2>&1
xorriso -indev "$iso" -report_el_torito as_mkisofs > out/inspection/boot-replay.txt 2>&1
fdisk -l "$iso" > out/inspection/partitions.txt
xorriso -osirrox on -indev "$iso" -extract / work/iso > out/inspection/extraction.txt 2>&1
find work/iso -type f -printf '%P\t%s\n' | sort > out/inspection/files.tsv
python3 scripts/manifest.py
python3 scripts/efi-audit.py
dpkg-query -W > out/inspection/tool-versions.tsv
du -B1 -s work/iso work/source > out/inspection/space.txt
cat out/inspection/report.md >> "$GITHUB_STEP_SUMMARY"
