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
checks out that build's revision, then runs every selected scenario against the
same local file. The slower full-install test is opt-in. Protected fixtures are
hashed before and after each VM. Smoke tests check bootability and real denied
writes; only the separate full-install scenario invokes the upstream installer.

The official [unattended interface](https://omarchy.org/manual/unattended-installs/)
uses a second drive labelled `cidata`. The released 4.0.6 ISO contains its loader.
Use that interface for reproducible VM installation configurations, after an
enforced write boundary is validated. An unattended configuration is an input,
not a storage safety boundary. Personal credentials must never enter public
artifacts. Use deferred provisioning for test seeds where supported.

The pure disk policy and preview wizard are separate from the upstream writer.
They do not authorize installation. Until cgroup device enforcement and the
complete upstream writer have passed destructive guest-only tests, development
images default to diagnostics and cannot be advertised as protected installers.

All heavy work is restricted by `cloud_only()` to GitHub-hosted Actions. Local
checks use only source text and synthetic Python dictionaries. QEMU attaches
regular files, never `/dev` paths from the runner. No privileged containers,
loop devices or runner-host partitioning are needed for fixture creation.
