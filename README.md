# Omarchy Secure Boot ISO Builder

GitHub Actions-first modification of the **official Omarchy 4.0.6 ISO** with a
guarded installer, a signed boot chain and retained stock recovery. All ISO
downloads, extraction, rebuilding and QEMU tests run on GitHub-hosted runners.
The original `lachthox/OmarchyInstaller` remains unchanged.

The current hardware milestone is **signed read-only validation**. Physical
installation remains disabled until a live boot confirms the Crucial BX500's
serial and the protected Samsung/WD disks. GPU unlock remains disabled.

Cloud tests have passed the actual guarded wizard, encrypted installation and
installed boot, forced writer interruption, enforcing Microsoft shim/MOK boot,
real pacman kernel signing hooks, a compiled and signed DKMS module, rejection of
a modified current UKI and keyboard selection of signed stock recovery.
Protected synthetic Windows disks remained byte-identical. See
[test results](docs/test-results.md) for evidence and remaining hardware limits.

Use the [release page](https://github.com/lachthox/omarchy-secureboot-iso/releases)
and follow [hardware validation instructions](docs/installation.md). The old
`v0.1.0-diagnostic.1` release is unsigned diagnostic media and is superseded for
the hardware milestone. A release labelled hardware-validation cannot install.

GitHub hosts the image in parts smaller than its 2 GiB per-asset limit.
`Get-OmarchyISO.ps1` resumes and verifies those downloads, reconstructs one ISO
and verifies its full SHA256. Flash that ISO with Rufus in **DD image mode**.
No external bucket is required. The release includes its public certificate,
fingerprints, build metadata and exact-image acceptance receipt.

For development, normal builds test the ISO on the build runner before uploading
it. The official ISO cache is keyed by SHA256 and reauthenticated on every hit.
Harness-only retests reuse an existing artifact with read-only source shares;
they do not rebuild the ISO. Source safety checks run separately and quickly.
Full installation and firmware tests run when relevant code changes or on demand.

See [architecture](docs/architecture.md), [security model](docs/security-model.md),
[recovery](docs/recovery.md), [release downloads](docs/release-hosting.md),
[upstream findings](docs/feasibility.md) and [GPU status](docs/gpu-unlock.md).
