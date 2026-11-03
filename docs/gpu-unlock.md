# Optional GPU Unlock 2.0

Source is pinned in `configs/gpu-unlock.json`. The reviewed revision's Arch
PKGBUILD builds `gpu-unlock-dkms` and `gpu-unlock-firmware` and verifies pinned
NVIDIA 610.43.03 inputs. No firmware or third-party binary is redistributed here.
RTX 3070 IDs 10de:2484 and 10de:2488 are the initial allowlist. Other models and
IDs are refused even when upstream supports them.

This feature is **not hardware-tested** and is never enabled by the live ISO.
`installer/gpu-unlock/prepare.sh` builds packages as an ordinary user on the
installed Arch system. It neither installs packages nor changes the boot entry.

Before installing the packages, retain a separate stock kernel/initramfs or UKI
and its signed boot entry. Never replace the only working boot artifact. The
upstream module does nothing without `gpu_unlock.targets=` in the embedded
kernel command line. A recovery UKI must omit that parameter; `module_blacklist=gpu_unlock`
can additionally prevent loading. Secure Boot entries must be regenerated and
signed rather than relying on editable external command lines.

Enable only a separate experimental entry targeting the specific PCI address.
The upstream mkinitcpio drop-in inserts `gpu_unlock` before `nvidia`. Check
presets using `-c` or `_config`: those bypass the drop-in. Use `lsinitcpio` to
verify module and firmware inclusion, and inspect the embedded UKI command line.

Under Secure Boot, DKMS must sign **both** GPU unlock and any NVIDIA DKMS modules
with a certificate the running kernel actually trusts. Firmware db enrollment,
MOK enrollment and kernel module trust are distinct. Verify `modinfo -F signer`,
the kernel trust keyrings, lockdown state, successful module loading and rejected
unsigned-module controls. A signer string alone is insufficient. Configure DKMS
`mok_signing_key`/`mok_certificate` only after the installed chain is validated.
Do not disable lockdown or signature enforcement to make the module load.

After kernel/driver updates, test the stock path first. Then verify DKMS rebuild,
signature, initramfs ordering, UKI signature and the separate experimental entry.
Update failures must retain the previous working stock artifact. Production
update hooks remain gated until this recovery behavior is tested.

Run `benchmark.py --label stock --output stock.json`, cold boot the experimental
entry, then repeat with `--label unlocked --output unlocked.json` in the same
PyTorch environment. The script records FP16/BF16 timing, driver, temperature,
power and clocks without changing limits. Compare repeated samples and inspect
kernel logs for success, timeouts, Xid errors, power management and resume.
These measurements are not yet available for the target RTX 3070.

[Pinned upstream source](https://github.com/Zagitta/gpu-unlock/tree/7eb51bccae0a0b7e599e084d971170e9a1e82d0c)
