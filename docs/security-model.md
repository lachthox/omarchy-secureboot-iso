# Security model

The diagnostic image is not a protected installation product. Pure policy tests
do not prove a privileged upstream installer cannot write the wrong disk.

The planned enforcement boundary must wrap both the configurator (its free-space
path already writes partitions) and the Python installer, including unattended
`cidata` entry. It must allow writes only to a freshly revalidated target and its
verified descendants. All other disks are protected by default, including
unknown disks. Block-device access must be kernel-enforced and tested with
attempted writes, not just filtered command names or a UI restriction. Existing
mounts, device-mapper descendants, hotplug and inherited descriptors need tests.
Production installation stays disabled until that boundary is implemented.

The policy requires model, serial, size and a stable by-id identity. Protected
models, Windows/BitLocker volumes, existing ESPs, mounted/mapped disks and
ambiguous identities are rejected. It is deliberately conservative: even a
previous Omarchy ESP requires manual review before reinstalling. Enumeration
changes alone must not change the chosen disk. The plan must be revalidated
immediately before writes and on topology changes. Logs must not contain
passwords, LUKS secrets, private keys or Tailscale tokens.

## Secure Boot

An OpenPGP-authenticated download is distinct from firmware Secure Boot trust.
Current diagnostic builds preserve upstream boot binaries, without promising
they boot under an enabled stock Windows Secure Boot policy.

Preferred research chain: a suitably licensed Microsoft-trusted shim, its matching
MokManager, a verifying second stage and machine-local signed UKIs. The entire
chain must enforce payload signatures, embedded initramfs and embedded command
line. Merely signing Limine does not prove it enforces every downstream input.
Unsigned payloads, altered cmdlines and revoked/SBAT-incompatible components
must fail in OVMF tests. Positive tests require firmware with the intended trust
database, not Secure Boot disabled or firmware in Setup Mode.

`sbctl` is useful for status, key and signing management, but its enrollment
commands are not executed automatically. Replacing PK/KEK/db is inappropriate
for the requested Windows-preserving defaults. Microsoft/OEM certificates must
be retained. Shim/MOK avoids replacing platform keys but still requires explicit
firmware-mediated public certificate enrollment and compatible downstream policy.

`prepare-local-keys.sh` optionally creates a per-machine owner key **only on an
encrypted installed root**. It never enrolls a key. Private keys remain root-only
on that encrypted root and must be backed up securely offline. Only public
certificates belong on the ESP or trust-enrollment medium. Never create or
publish user signing credentials in Actions. VM test keys must be ephemeral and
must not enter artifacts or caches.

Guided trust enrollment must display the exact public certificate fingerprint,
explain the MOK/firmware approval screen and provide an abort path. No TPM clear,
BitLocker protector change, Windows BCD edit or platform-key reset is automated.
The project makes no Vanguard compatibility claim.

Sources: [upstream Secure Boot design](https://github.com/omacom/omarchy-iso/blob/ef1d3897f63f2e0104e461f7bf0d4bb0456168c9/plans/consumer-secure-boot.md),
[sbctl](https://github.com/Foxboron/sbctl),
[Limine configuration](https://github.com/Limine-Bootloader/Limine/blob/trunk/CONFIG.md).
