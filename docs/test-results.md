# Verified cloud results — 7 November 2026

All ISO operations and destructive tests ran on GitHub-hosted runners. Tests
used synthetic regular-file-backed QEMU drives, never host block devices.

| Evidence | Result |
| --- | --- |
| [Official ISO inspection](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/41607119230) | Official 4.0.6 SHA256 and OpenPGP signature passed; real layout captured |
| [Diagnostic build and boot tests](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/41612475689) | Modified official ISO built; hidden ESP byte-identical; CD, USB and reordered disk boots passed |
| [Full upstream installation](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/41615225482) | Official unattended loader and installer completed in a kernel device sandbox |
| [Installed-system and failure tests](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/41620323819) | Installed target booted without ISO; invalid target rejected; actual package-writing installation forcibly killed; protected disk hashes and synthetic Windows NVRAM entry preserved |
| [EFI signature audit](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/41619819083) | Both original EFI bootloaders have no signature tables; appended FAT ESP is 24 MiB |
| [Locked-tool inspection](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/41621343503) | Exact analysis tool package versions installed and real inspection passed |
| [Windows downloader checks](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/41618808822) | Exact reconstruction, corruption/tamper rejection, no overwrite, partial cleanup and parallel range reconstruction passed |
| [Published diagnostic release](https://github.com/lachthox/omarchy-secureboot-iso/releases/tag/v0.1.0-diagnostic.1) | Five GitHub-hosted parts, manifest, Windows helper, full/per-part checksums and metadata published |
| [Actual guarded wizard](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/41642803574) | Read-only audit and unencrypted install/installed boot passed; encrypted installation completed but its reboot timed out at the passphrase prompt; interruption case was skipped |
| [Actual signed live payload](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/41642803460) | Complete live acceptance passed with enforcing OVMF, authenticated live root and Microsoft shim/MOK trust; this is not installed-system or hardware acceptance |
| [Corrected guarded wizard acceptance](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/41645933032) | Read-only audit, actual unencrypted/encrypted installation and installed boot, and forced writer interruption passed |
| [Actual signed installed-system acceptance](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/41653839295) | Real encrypted installed-system key generation/signing/update, signing-failure preservation, Microsoft shim/MOK enforcing boot, intact-PE initramfs tamper rejection and independent recovery boot passed |
| [Current diagnostic image](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/41655316192) | Rebuilt image verified, runner-local VM smoke tests passed, and diagnostic-iso artifact uploaded with the read-only hardware-validation menu entry; not signed physical-installation media |
| [Signed read-only hardware image](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/42246446355) | Official ISO authenticated, rebuilt and signed with an ephemeral live key; actual writable USB clone booted with SecureBoot=1/SetupMode=0; keyboard-operated audit completed and all three simulated SSDs stayed unchanged |
| [Real owner enrollment, audit and modified-root rejection](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/42247038530) | Actual MokManager disk enrollment and cancellation passed with displayed fingerprint comparison; PK/KEK/db/dbx unchanged; enrolled firmware booted that exact image into the audit; a modified external SquashFS was rejected before mount; all simulated disks unchanged |
| [Final guarded signing and first secure boot](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/42248036346) | Actual wizard installed encrypted target with OMARCHY_OS ESP, generated the owner key inside its restricted writer, published both public fingerprints/enrollment receipt, initialized signed current/recovery and hooks, then booted with SecureBoot=1/SetupMode=0 and module integrity enforced; package/DKMS/tamper/recovery suite also passed |

The low-level sandbox tests actually attempted writable opens on both protected
disks and their partitions, including aliases for the same device numbers. Those
opens were denied. The selected target accepted a real write. The full upstream
writer ran under the same device policy. After installation, the VM booted from
the target with the ISO removed. SHA256 checks covered both protected image files
before and after these operations. The invalid-target case also hashed the target.
Final cleanup checks protected hashes even after a failed test.

The full-install adaptations are version-checked: keyboard enumeration reads
local keymap files instead of D-Bus, and archinstall uses classic chroots instead
of asking systemd to launch processes outside the device sandbox. A private PID
namespace preserves correct chroot detection; the installation service blocks
BPF/ptrace syscalls and cannot access the privileged systemd/D-Bus sockets.
The guarded wizard now uses these adaptations in its restricted writer.
Acceptance still supplies synthetic disks and a read-only source share; the
physical-installation capability remains disabled.

## Measured feedback speed

Latest successful test timings on a standard runner:

| Scenario | Seconds |
| --- | ---: |
| CD boot and denied-write controls | 30.32 |
| USB boot and denied-write controls | 26.75 |
| Changed disk order | 29.12 |
| Invalid target rejection | 29.17 |
| Full install plus installed-system boot | 179.51 |
| Forced interruption during real package writes | 53.02 |

The default fast suite totals **115.36 seconds**. Full installation/fault testing
is opt-in. A fresh retest runner's artifact transfer, SHA256 verification and
extraction measured 99 seconds with eight HTTP ranges, compared with 375 seconds
in the preceding single-transfer run. These are observations, not guarantees
across runner load or regions. Normal build tests need no artifact transfer at
all: they use the already-built local ISO. Harness-only changes use a read-only
test-source share and do not rebuild the ISO.

## Remaining production gates

The old v0.1 diagnostic prerelease is unsigned. The new hardware milestone is
signed **read-only validation**, with physical installation disabled. Its owner
MOK enrollment preserves platform trust databases. Actual motherboard revocation
policy and the user's Crucial/Samsung/WD identities remain hardware checks.

The accepted hardware image SHA256 is
`fb35b4349bcaccab200e80ed0aa316186c0f14378d4915289b652b2830f5c594`.
Its public certificate SHA256 is
`532fc18535433629298ee295ed0b566f70bbb03ddedfc88d344c17b5a3c4685d`.
The release gate checks both against the immutable build artifact and acceptance
receipt. Only public certificate material is published; the live private key
was discarded after signing.

The real guarded wizard has installed and booted unencrypted and encrypted
synthetic targets; its interrupted-writer test also passed.
The [final guarded-wizard run](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/42248036338)
repeated read-only audit, both installations/boots and writer interruption after
the named target ESP and enrollment receipt changes.
The passphrase driver now waits for the complete cryptsetup prompt and allows
terminal setup to finish before sending input: cryptsetup prints the prompt
before disabling echo with TCSAFLUSH, which can discard an immediate response.
The signed installed-system chain, real package-manager update hooks, generic
DKMS signing/loading and keyboard selection of signed recovery have passed in
[the November 7 package-policy run](https://github.com/lachthox/omarchy-secureboot-iso/actions/runs/42240457496).
That run reinstalls the official kernel through pacman, builds and loads an
owner-signed DKMS module, rejects a modified current image and boots stock
recovery selected from the signed menu. Both protected disk hashes remain
unchanged. The actual NVIDIA driver and motherboard remain hardware checks.

The **Actual installed-system signing and recovery acceptance** workflow now
exercises the real machine-local key-generation and update scripts on the
encrypted installed guest. It checks a successful update and a signing failure,
then boots the signed current and independent recovery UKIs through Microsoft
shim/MOK and rejects a modified initramfs. Its tooling share is read-only; the
ephemeral private key stays inside the disposable encrypted target, which is not
uploaded. The November 3 run did not test interactive MOK enrollment, menu
selection or package-manager hooks. The November 7 run adds the latter two.
Recovery retains its initial UKI and module tree. Kernel reinstall is tested;
upgrades across different kernel versions need additional acceptance.

GPU Unlock remains disabled; source preparation, compatibility checks, recovery
design and benchmark tooling exist, but target RTX 3070 performance/thermal/power
measurements have not been taken. These tests do not establish real Windows,
BitLocker, motherboard firmware or Vanguard compatibility. Follow the separate
physical-validation procedure before any real-hardware installation claim.
