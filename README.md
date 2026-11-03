# Omarchy Secure Boot ISO Builder

Experimental, GitHub Actions-first modification of the **official Omarchy ISO**.
All ISO downloads, extraction, modification, rebuilding and VM tests run on
GitHub-hosted runners. The original `lachthox/OmarchyInstaller` is unchanged.

Repository: [lachthox/omarchy-secureboot-iso](https://github.com/lachthox/omarchy-secureboot-iso).

Start with **Actions → Inspect official Omarchy ISO → Run workflow**. The workflow
authenticates the pinned official ISO using both its release checksum and its
OpenPGP signature, records boot structures and reads installer sources without
executing them. Inspection artifacts and runner resource measurements are retained.

The production installer, Secure Boot chain and GPU unlock are not validated yet.
Do not use development images to install on physical hardware. No private signing
keys are distributed. No local physical disks are accessed by development tooling.

For a build, run **Build diagnostic Omarchy ISO**. Normal runs test the ISO on the
same runner before uploading it once: no ISO downloads between boot scenarios.
The slower full unattended-install test is opt-in and does not block a separate
quick build. **Retest an existing ISO artifact** downloads once for all scenarios.

Actual inspection and diagnostic rebuilding have succeeded. The original hidden
ESP is byte-identical after rebuilding. Virtual acceptance results remain the
authority for which tests passed; a successful build alone does not prove an
installation is safe. See [measured findings](docs/feasibility.md),
[architecture](docs/architecture.md), [security model](docs/security-model.md),
[installation](docs/installation.md), [recovery](docs/recovery.md) and
[release downloads](docs/release-hosting.md).

Releases use GitHub directly, like the original project. Because this ISO exceeds
GitHub's 2 GiB per-file limit, Actions publishes smaller parts plus
`Get-OmarchyISO.ps1`. Run that helper to obtain one checksum-verified ISO for
Rufus. No external bucket is required. Diagnostic images are visibly labelled
prereleases and are refused by the production release gate.
