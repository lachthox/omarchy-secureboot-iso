# Recovery

Development images default to non-installing diagnostics. Preserve build metadata,
cloud reports and QEMU serial logs when reporting failures. Live logs disappear
on reboot unless explicitly copied to a separately selected destination; do not
automatically save them to a Windows ESP or data disk.

If an eventual installation is interrupted, do not automatically resume disk
writes. Rediscover every disk, compare stable identities and require a new plan
confirmation. Only the already selected target may be repaired. Do not run a
generic boot repair against every connected ESP. Use the motherboard's Windows
Boot Manager entry to test Windows separately.

For GPU issues, cold boot the retained stock UKI without `gpu_unlock.targets=`.
If the module reports firmware timeouts or retained DMA buffers, power the machine
fully off before retrying. Remove the optional packages from the stock boot and
rebuild/sign boot artifacts only after verifying a working recovery artifact.

For Secure Boot failures, use an already trusted recovery environment. Inspect
certificate fingerprints, signature verification, key enrollment state and SBAT
revocations. Do not clear TPM, replace platform keys or disable Windows security
as an automatic recovery action. Re-enrollment and firmware choices remain guided
owner actions.
