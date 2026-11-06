# Architecture and milestone boundaries

The source is the authenticated, published Omarchy 4.0.6 ISO, not an Arch ISO
and not a package reconstruction. Its exact SHA256 is in `configs/upstream.json`.
The independent original project is read only during research.

`inspect-upstream.yml` downloads once, verifies official release metadata,
SHA256 and OpenPGP signature, and records inert filesystem and boot information.
The SHA256-keyed cache is reauthenticated on every hit.

`build-iso.yml` repeats authentication, checks release-specific installer hashes,
extracts the original SquashFS with root ownership, injects diagnostics, rebuilds
the live filesystem and replays the original xorriso boot equipment. It compares
the original and rebuilt hidden ESP bytes. Original installer source is untouched
in the diagnostic milestone. No upstream script is run on the build host.

The build runs the shared `.github/actions/vm-test` component against the ISO
already on its runner, before uploading it. No test downloads are needed in the
normal pipeline. CD-ROM, USB and reordered-device scenarios run sequentially,
reusing the immutable ISO with fresh regular-file-backed disks and OVMF state.
This avoids three multi-gigabyte downloads and keeps guest RAM within the
standard runner's capacity. Pure policy checks run independently.

`test-iso.yml` is for standalone retesting: it downloads an artifact **once**,
uses the selected workflow revision's test harness, then runs every selected
scenario against the same local file. Both the image and harness commits are
recorded. A read-only virtio-9p share exposes only `tests/qemu` inside the VM, so
test-only edits do not require repacking the ISO. The image must support test
protocol 1; older proof images need one rebuild. The slower full-install test is
opt-in. Protected fixtures are
hashed before and after each VM. Smoke tests check bootability and real denied
writes; only the separate full-install scenario invokes the upstream installer.

The official [unattended interface](https://omarchy.org/manual/unattended-installs/)
uses a second drive labelled `cidata`. The released 4.0.6 ISO contains its loader.
Use that interface for reproducible VM installation configurations, after an
enforced write boundary is validated. An unattended configuration is an input,
not a storage safety boundary. Personal credentials must never enter public
artifacts. Use deferred provisioning for test seeds where supported.

The guarded wizard passes a freshly revalidated plan to the restricted upstream
writer. Its actual encrypted/unencrypted installations, protected-device denials
and interruption tests have passed. The writer also finalizes machine-local
signing and target-local recovery. Physical release capabilities remain disabled
until the read-only hardware boot confirms the actual disks.

`build-hardware-validation.yml` authenticates and repacks the official live
filesystem, embeds root authentication in the signed UKI, replaces the appended
EFI partition with a signed shim/MokManager/UKI chain, and replays original hybrid
boot equipment. It discards the ephemeral live signing key. The public certificate
is carried on the EFI partition and in build metadata. The physical audit runs
with every block device read-only. Enrollment/audit retests reuse this exact
image through `audit-acceptance.yml`; release receipts bind its SHA256 and public
certificate to the successful firmware UI and tamper tests.

All heavy work is restricted by `cloud_only()` to GitHub-hosted Actions. Local
checks use only source text and synthetic Python dictionaries. QEMU attaches
regular files, never `/dev` paths from the runner. No privileged containers,
loop devices or runner-host partitioning are needed for fixture creation.
