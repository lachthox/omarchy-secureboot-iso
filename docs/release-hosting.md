# GitHub Releases, without a storage bucket

The original OmarchyInstaller release uploaded a 1,629,945,856-byte ISO directly
to GitHub. The official Omarchy derivative is about 6.5 GB, beyond GitHub's
2 GiB limit per asset. The selected design keeps all hosting on GitHub:

1. Actions verifies the successful build/test run and the ISO checksum.
2. It splits the ISO into parts no larger than 1,500,000,000 bytes.
3. It generates a manifest containing the full and per-part SHA256 checksums.
4. It generates `Get-OmarchyISO.ps1`, with the manifest hash embedded.
5. It uploads every asset to a draft release, then publishes it.

Download the helper from the release and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Get-OmarchyISO.ps1
```

It downloads and verifies the parts, joins their bytes into one ISO, checks the
full SHA256 and renames it to its final `.iso` name only on success. Cached parts
allow retrying a download without obtaining every part again. It never overwrites
a different existing ISO. It removes its downloaded parts after success unless
`-KeepParts` is supplied. Allow about twice the ISO size in free space. This is
file reconstruction, not ISO extraction, modification or rebuilding.

`-OutputDirectory` chooses where the ISO is written. For manually downloaded
assets, `-LocalAssetsDirectory` reads the manifest and parts from that directory.
The same checksum rules apply. No administrator rights, storage credentials,
partition access or USB flashing operations are used by the helper.

The generated helper is tested on a GitHub-hosted Windows runner using small
synthetic files: exact reconstruction, repeat execution, corrupt parts, altered
manifests, an existing conflicting ISO and final-hash failure cleanup.

`release.yml` supports diagnostic prereleases and production releases. Diagnostic
prereleases must be clearly labelled and must not be used as protected installers.
Production publication additionally requires validated disk protection, a full
installation and Secure Boot support. These production gates remain closed.

Sources: [previous release](https://github.com/lachthox/OmarchyInstaller/releases/tag/v0.1.11),
[GitHub release limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).
