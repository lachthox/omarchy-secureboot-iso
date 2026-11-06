# Read-only hardware validation

The next boot confirms the actual Crucial BX500 CT1000BX500SSD1 and protected
Samsung/WD disks before any partitioning. Windows drive letters do not exist in
the Linux live environment; select by model, complete serial and stable by-id.
The hardware-validation image disables installation and launches the actual
guarded wizard with kernel-denied block-device writes, including to the target.

1. Open the [GitHub releases](https://github.com/lachthox/omarchy-secureboot-iso/releases)
   and choose the **hardware-validation** prerelease. The old diagnostic release
   is unsigned and is not the image for this boot.
2. Download `Get-OmarchyISO.ps1` and run it from that download directory:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\Get-OmarchyISO.ps1
   ```

   It verifies every part and the final ISO. Allow approximately twice the ISO
   size in free space. The execution-policy choice applies only to this process.
3. In Rufus, carefully select a spare **16 GB or larger USB**, select the resulting
   ISO, and use **DD image mode**. This erases that USB. Keep the Samsung, WD and
   Crucial connected for the read-only inventory; do not select any SSD in Rufus.
4. Keep Secure Boot enabled. Use the motherboard's one-time **UEFI USB** boot
   entry, preserving the existing Windows Boot Manager entry. Keep Windows
   recovery information available before firmware boot changes.
5. On first boot, shim should report a verification failure for the untrusted
   build certificate. Enter MokManager, choose **Enroll key from disk**, select
   the USB's **OMARCHY_SB** volume, and browse **EFI → BOOT → omarchy-live.cer**.
   Choose **View key**, and compare its fingerprint with the release's
   `CERTIFICATE-FINGERPRINTS.txt`. MokManager 15.8 displays SHA1; the release also
   publishes SHA256. If it differs, cancel. Continue, confirm and reboot the same
   USB. This enrolls only a public MOK and leaves PK/KEK/db/dbx intact.
6. Photograph the complete inventory before proceeding. Select the Crucial by
   number or stable by-id, and type its complete serial. Photograph the resulting
   plan showing the Crucial destination and the Samsung/WD protected identities.
   The audit must finish with `READ_ONLY_HARDWARE_VALIDATION_COMPLETE`.
7. The JSON receipt stays in RAM at `/run/omarchy-hardware-validation.json`.
   If the shell prompt returns, `cat /run/omarchy-hardware-validation.json` shows
   its firmware state and identities. No receipt is saved automatically to an SSD;
   it disappears on reboot. Shut down and return to Windows Boot Manager.

Share the actual inventory and receipt for review before enabling installation.
The intended destination is the entire Crucial SSD formerly containing E:;
whole-disk installation will erase all of its partitions. This audit does not
perform that operation.

If the firmware rejects the Microsoft-signed shim itself, stop. A motherboard's
dbx/SBAT policy may require a newer compatible chain. Do not replace platform
keys, clear TPM or disable validation to bypass a failure.

## Installation after hardware review

The implemented writer revalidates identities and runs the upstream installer
inside a kernel device boundary. It creates an encrypted target root and a
target-local ESP, generates the owner signing key inside that encrypted root,
and installs signed current/recovery images and package hooks. The installed
owner certificate is different from the live audit certificate and requires its
own guided enrollment before the installed signed chain can boot. Select the
**OMARCHY_OS** volume in MokManager and compare the displayed SHA1 fingerprint
with the writer's enrollment receipt before confirming that owner key.

Physical release capabilities remain disabled pending the audit. CI cannot
establish real Windows, BitLocker, motherboard, NVIDIA or Vanguard compatibility.
See [recovery](recovery.md) and [verified test scope](test-results.md).
