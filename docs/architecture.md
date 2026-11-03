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

`test-iso.yml` downloads the build artifact and boots it under OVMF with three
regular-file-backed virtual disks. CD-ROM, USB and reordered-device scenarios
run independently. Protected fixtures are hashed before and after the VM runs.
The first milestone checks startup/presence, **not a successful installation**.

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
