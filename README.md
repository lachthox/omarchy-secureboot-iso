# Omarchy Secure Boot ISO Builder

Experimental, GitHub Actions-first modification of the **official Omarchy ISO**.
All ISO downloads, extraction, modification, rebuilding and VM tests run on
GitHub-hosted runners. The original `lachthox/OmarchyInstaller` is unchanged.

Start with **Actions → Inspect official Omarchy ISO → Run workflow**. The workflow
authenticates the pinned official ISO using both its release checksum and its
OpenPGP signature, records boot structures and reads installer sources without
executing them. Inspection artifacts and runner resource measurements are retained.

The production installer, Secure Boot chain and GPU unlock are not validated yet.
Do not use development images to install on physical hardware. No private signing
keys are distributed. No local physical disks are accessed by development tooling.
