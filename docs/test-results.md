# Verified cloud results — 3 November 2026

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
These adaptations currently run in the **VM harness**, not a production wizard.

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

The public prerelease is **diagnostic only**. It is not an installation product
for the target desktop and will not boot under an unmodified stock Secure Boot
policy. Do not weaken Windows security to use this prototype.

The real interactive installer must integrate the tested write boundary with
the model/serial/by-id policy, including encrypted device-mapper descendants and
recovery. The current preview wizard does not install. The signed live/installed
boot chain, authenticated live root, owner trust enrollment, update signing and
NVIDIA module signing still require implementation and acceptance tests.

GPU Unlock remains disabled; source preparation, compatibility checks, recovery
design and benchmark tooling exist, but target RTX 3070 performance/thermal/power
measurements have not been taken. These tests do not establish real Windows,
BitLocker, motherboard firmware or Vanguard compatibility. Follow the separate
physical-validation procedure before any real-hardware installation claim.
