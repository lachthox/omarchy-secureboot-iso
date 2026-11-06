# Security model

The guarded wizard retains the official Omarchy installer, adapted through
version-checked patches. Installation runs in a dedicated systemd cgroup with
kernel device restrictions: the confirmed target and its verified descendants
may be written; every other disk is read-only. Private mount/PID namespaces,
blocked privileged D-Bus/systemd sockets and BPF/ptrace restrictions keep the
upstream writer inside that boundary. A separate bounded preparation stage
creates only the target's encrypted mapping. Topology changes stop the writer.

Policy requires model, serial, capacity and a stable by-id identity. Samsung and
WD protected models, Windows/BitLocker volumes, existing ESPs, mounted/mapped
disks and ambiguous identities are refused. Explicit whole-disk erasure can
allow ordinary data partitions on the Crucial, but cannot override protected
identities or a Windows boot partition. Even an interrupted installation's
existing ESP requires review before reinstalling.

Actual guest tests attempt protected writable opens, including device aliases,
run the real upstream writer, interrupt real package writes and hash protected
fixtures before and after. They do not identify the user's actual disks.
Physical installation remains disabled until the read-only hardware boot
confirms their identities.

## Secure Boot

The implemented chain is Microsoft-signed Ubuntu shim 15.8, its matching
MokManager, an owner-signed UKI or signed systemd-boot menu, and an owner-signed
kernel with embedded initramfs and command line. Kernel module signatures and
integrity lockdown are mandatory. The live UKI authenticates the exact SquashFS
copy in RAM before mounting it. Actual enforcing OVMF tests supplement small
firmware fixtures for modified payload and command-line rejection.

The hardware audit media carries only a public build certificate. Its ephemeral
private key is generated outside the live filesystem and discarded after
signing. The installed system generates a different machine-local owner key on
its encrypted root; that private key stays root-only there. Only its public
certificate is copied to the Crucial's ESP for explicit owner enrollment.

No workflow replaces PK/KEK/db/dbx, clears TPM, edits Windows BCD, changes
BitLocker protectors or automatically enrolls trust. Enrollment is a physical
MokManager confirmation, with a displayed public fingerprint and cancellation.
A firmware dbx/SBAT policy can reject the pinned shim: this requires a compatible
updated chain. Windows/BitLocker and Vanguard behavior cannot be established
by CI.

The normal wizard also checks active SecureBoot=1, SetupMode=0, shim validation,
module signature enforcement and kernel lockdown before collecting installation
credentials. Release capabilities separately keep physical installation closed.

## Updates and recovery

Pacman pre-transaction checks verify keys and both existing signed boot images;
failure aborts the transaction. The post-transaction hook signs external modules,
builds an embedded UKI, verifies it and atomically publishes current. The initial
stock recovery UKI and its module tree are retained. The signed menu offers
current and stock recovery; unsigned upstream-generated entries are retained
outside automatic discovery. Unsigned fallback deployment hooks are masked so
normal package updates cannot silently replace the signed shim.

Failed signing preserves the previous verified current and recovery images.
The ESP publication path uses locking, staged files and durability checks.
Power loss during a package transaction still needs target recovery testing.

Passwords, LUKS secrets, private keys and personal provisioning tokens must never
enter release artifacts, caches or logs. No local physical disk is accessed by
development tooling. Heavy work and destructive fixture tests are restricted
to GitHub-hosted runners and regular-file-backed QEMU disks.

References: [MokManager 15.8](https://github.com/rhboot/shim/blob/15.8/MokManager.c),
[upstream Omarchy consumer Secure Boot design](https://github.com/omacom/omarchy-iso/blob/ef1d3897f63f2e0104e461f7bf0d4bb0456168c9/plans/consumer-secure-boot.md).
