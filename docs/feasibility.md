# Findings from actual inspection

Evidence: [successful inspection run 41607119230](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/41607119230).

* Omarchy version: 4.0.6, official SHA256
  `b542db5fecc37395d9af6654a8146ebed225f275ae4d5a6fcf432e40afe7bb88`.
* OpenPGP: good EDDSA signature by pinned primary fingerprint
  `40DFB630FF42BCFFB047046CF0134EE680CAC571`, signed October 19, 2026.
  The fingerprint is documented in the official ISO repository; HTTPS and the
  reviewed fingerprint remain trust anchors, not independent transparency proof.
* ISO size: 6,448,529,408 bytes (3,148,696 ISO blocks plus final image padding as
  measured by the download; consult artifact metadata for exact file size).
* Volume label `OMARCHY_202610`; hybrid MBR/GPT; BIOS syslinux and UEFI El Torito.
* EFI image is **hidden and appended**, 49,152 sectors of 512 bytes (24 MiB).
* One live filesystem: `arch/x86_64/airootfs.sfs`, 6,129,025,024 bytes,
  SquashFS 4.0, zstd level 19, 1 MiB blocks, 103,065 inodes.
* The boot directory contains `vmlinuz-linux-t2` and its initramfs. Boot paths
  must be obtained from this image, not copied from newer upstream source.
* Entrypoints: `/root/.automated_script.sh`, `/root/configurator`,
  `/usr/local/bin/omarchy-iso-install`, Python orchestrator under
  `/usr/share/omarchy-iso`. `omarchy-cidata-load` exists.
* The released installer uses archinstall and offline packages. The later
  upstream source snapshot uses a prebuilt Btrfs root image; **that is not the
  released 4.0.6 layout**. Compatibility is bound to ISO-contained hashes.

## Runner measurements

First inspection ran on standard `ubuntu-24.04`: four CPUs, 16,759,308,288 bytes
RAM, 91,749,933,056 bytes initially free. Download plus verification: 53.62 s.
Inspection plus ISO tree extraction: 26.85 s, peak RSS 59,308 KiB.
Extracted ISO tree used 6,423,158,784 bytes. Source used 6,448,541,696 bytes
including signature. Build resource reports separately measure full root
extraction and recompression. Inspection success does not prove build/test sizing.

[GitHub documents](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
14 GB guaranteed SSD capacity for standard runners. The measured image has much
more free space, but this is not a guarantee. A build preflight requires 40 GB
free. If that fails, configure a larger **GitHub-hosted** runner; do not fall back
to the desktop. CPU/memory limits are bounded to four squashfs workers and 4 GiB.
The first complete diagnostic rebuild took 87.20 s, with peak RSS 3,312,356 KiB.
Full root extraction used 7,545,491,456 bytes and took 17.18 s. That build retained
58,637,012,992 free bytes at its final-space measurement, so a larger runner was
not required for this measured workload. VM installation resources are measured
separately. Artifact distribution was substantially slower than guest startup;
the normal pipeline now tests in the build workspace before uploading once.

The transformation and VM tool packages are version-locked in
`configs/tools-ubuntu24.json`, using versions measured in successful runs.
Unavailable versions fail instead of silently upgrading. Transitive packages,
GitHub CLI/Python and runner image metadata are also recorded; the full hosted
OS image is not claimed to be immutable or byte-reproducible across updates.

## Release and Secure Boot blockers

GitHub Releases limits a single asset to 2 GiB (see its storage/bandwidth quota
documentation). This ISO exceeds that. A single directly flashable ISO needs
external object hosting, or reconstruction from multiple release assets. After
reviewing the original repository's 1.63 GB release, the selected approach is
GitHub-hosted parts plus a Windows download helper. The helper produces one
checksum-verified ISO for Rufus; this adds one explicit step to the original
download-to-Rufus flow. No external bucket is required. Actions artifacts also
retain proof images but are not a permanent public release CDN.

The official ISO Secure Boot plan is a proposal, not evidence of a shipped
Microsoft-trusted chain. Signing a custom EFI file or a UKI does not make a
stock Windows firmware trust it. Preserve Microsoft/OEM trust and TPM state;
do not silently enroll replacement keys. Production Secure Boot release remains
blocked pending verified boot policy, trust enrollment and update/recovery tests.

Sources: [official release](https://github.com/omacom/omarchy/releases/tag/v4.0.6),
[official ISO sources](https://github.com/omacom/omarchy-iso),
[upstream consumer Secure Boot plan](https://github.com/omacom/omarchy-iso/blob/ef1d3897f63f2e0104e461f7bf0d4bb0456168c9/plans/consumer-secure-boot.md).
