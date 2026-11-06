# Secure Boot acceptance gates

The current UEFI boot matrix uses OVMF without pre-enrolled consumer keys. It
proves UEFI bootability only. It must never be reported as a Secure Boot pass.

Required before enabling a production Secure Boot profile:

* Boot the complete image with SecureBoot=1, SetupMode=0 and the intended
  Microsoft/OEM/MOK trust model. Capture guest variable values and OVMF settings.
* Reject unsigned/replaced EFI second stages and unsigned/replaced UKIs.
* Reject modified initramfs and external command-line substitutions.
* Test SBAT revocation and interrupted key enrollment/update recovery.
* Verify signed NVIDIA/GPU unlock modules load; unsigned controls fail under
  the actual kernel's enforcement policy.
* Retain a working, signed stock UKI after an update/signing failure.

The signed live payload has passed the Microsoft shim/MOK test; see
[recorded evidence](../../docs/test-results.md). The installed-system workflow
uses the real signing/update code on an encrypted synthetic target, including
failure preservation and independent recovery boot. Do not equate adding this
test with passing it, or pre-enrolled VM MOK with interactive enrollment.
The remaining criteria above still gate production. Ephemeral VM private keys
must not be uploaded.
