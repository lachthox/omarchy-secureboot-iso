# Patch policy

The diagnostic milestone injects a systemd service and diagnostic utility and
adds a separate GRUB entry. It preserves the original installer bytes. See
`scripts/patch-iso.sh` and `scripts/patch-grub.py` for the complete transformation.

Every future upstream-source patch must require matching ISO-contained hashes
from `configs/compatibility.json`. Reject a mismatch; never fuzzy-apply a storage
or Secure Boot patch to an unknown version. New official releases are inspected
first, then receive a reviewed compatibility profile.
