# Development image use

1. Download the **diagnostic-iso** artifact from a successful build run. This is
   a ZIP containing an ISO, SHA256SUMS and build metadata. Extract the ZIP first.
2. Verify the ISO SHA256 against SHA256SUMS before flashing.
3. For physical validation only after VM acceptance, use Rufus's DD image mode
   to preserve the hybrid partition/EFI structure exactly. This has not yet been
   tested with a real USB stick or motherboard.
4. The default menu entry performs diagnostics and powers off. Original Omarchy
   entries are preserved for upstream comparison and do not yet enforce this
   project's Windows protection. Do not use those entries on the target desktop.

The intended production sequence is select Crucial BX500 by stable identity,
confirm its serial and the partition plan, install with an enforced write
boundary, verify a target-local ESP, complete guided trust enrollment, then
optionally enable GPU unlock in a separate boot entry. That sequence remains a
gated development objective, not the current image's behavior.

## Physical validation required before calling an installer safe

Back up Windows data and independently retain BitLocker recovery information.
Record baseline Windows boot/TPM/Secure Boot state and all disk identities.
Validate on sacrificial disks before attaching valuable data. Confirm Windows
and data disks remain byte-identical, Windows BCD/ESP unchanged, the Omarchy ESP
belongs to the Crucial disk, Windows still boots and recovery remains available.
Exercise firmware trust enrollment/cancellation, updates, interrupted installs,
GPU normal/unlocked/recovery boots, thermals and power management. No CI fixture
can establish real Windows, BitLocker, firmware or Vanguard compatibility.
