# Reuse review: lachthox/OmarchyInstaller

The existing repository was inspected through read-only GitHub API requests.
No commit, branch, issue, release or workflow was changed there.

* `windows-prep.ps1`: retain the concepts of explicit plans, hardware identity,
  BitLocker checks and troubleshooting logs. Do not carry automatic Windows
  partition preparation into development runs. This project does not need a
  Windows executable to prepare an ISO.
* `build-custom-iso.sh`: useful filesystem discovery and xorriso experience,
  but its documented source is vanilla Arch and it allows workstation builds.
  Both conflict with this project's requirements. The new pipeline uses the
  authenticated official Omarchy ISO and a cloud-only guard.
* `rebuild/tools/build_iso_pipeline.py`: separates orchestration from YAML and
  produces metadata, but its `ARCH_MIRROR_DEFAULT` selects vanilla Arch. The
  downloader and trust model were replaced rather than reused.
* `rebuild/installer/platforms/linux_live/identity.py` and `install.py`: stable
  identity, plan contracts and staged install state are useful techniques.
  Orchestration scaffolding alone is not an enforced disk-write boundary.
* `.github/workflows/rebuild-iso.yml`: useful artifact handoff pattern; this
  repository additionally pins Actions, authenticates every source cache hit,
  measures resources and locks the actual upstream installer layout.

No original project code has been copied at this stage. Techniques were reused
in newly written code. Source licenses still apply to upstream ISO contents and
any future copied code; the repository's MIT license covers our own tooling.

[Reviewed project](https://github.com/lachthox/OmarchyInstaller)
