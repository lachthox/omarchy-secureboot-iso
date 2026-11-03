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

Tests are pending. This file records acceptance criteria; it is not evidence
that any of them passed. Ephemeral VM private keys must not be uploaded.
