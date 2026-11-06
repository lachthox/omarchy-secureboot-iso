# Recovery

The signed installed-system menu offers **Omarchy** and **Omarchy stock recovery**.
Use the arrow keys to select stock recovery if an updated current image fails.
The menu editor is disabled. Recovery retains the initial signed stock UKI and
its kernel modules; GPU unlock remains disabled. Actual VM acceptance modifies
the current image, confirms rejection, selects recovery from this menu and
boots the encrypted root with Secure Boot and module enforcement active.

Signing hooks run during normal pacman kernel/module/systemd changes. Before
updates they verify the machine-local key and both boot images. After updates
they sign modules and publish a verified current UKI. An invalid signing key
must leave the previous current and recovery images intact. Inspect hook errors
before rebooting after any failed transaction.

From a working installed system, check the policy with:

```sh
sudo python /usr/local/lib/omarchy-custom/secureboot/manage.py preflight
```

After fixing the reported package/key problem, rebuild through the same policy:

```sh
sudo python /usr/local/lib/omarchy-custom/secureboot/manage.py update
```

Do not overwrite recovery with a failing current image. Back up the machine-local
private key securely offline from `/var/lib/omarchy-custom/keys`; keep it private.
The public enrollment file is `/boot/EFI/BOOT/omarchy-owner.cer`. It differs from
the live USB's `omarchy-live.cer`. The installed ESP is labelled **OMARCHY_OS**.
The writer displays both SHA256 and MokManager's SHA1 fingerprint; the local
public enrollment receipt is `/etc/omarchy-custom/enrollment.json`.

If installation is interrupted, rediscover all disks and review the target's
existing layout before repairing it. Do not automatically resume formatting or
run generic boot repair against every ESP. The Crucial's target-local fallback
bootloader does not require replacing the Samsung's Windows boot files or
reordering Windows NVRAM entries. Use the motherboard's existing Windows Boot
Manager entry to test Windows independently.

For trust failures, check the public certificate fingerprint, MOK enrollment,
signatures and firmware dbx/SBAT revocations from a trusted environment. Do not
clear TPM, replace platform keys or disable Windows security as an automatic
repair. Hardware firmware acceptance and Windows compatibility remain separate
validation steps.

The read-only hardware audit does no installation or repair. Its JSON report is
in RAM at `/run/omarchy-hardware-validation.json`; photograph or read it before
rebooting. It is not automatically saved to a Windows ESP or data disk.
