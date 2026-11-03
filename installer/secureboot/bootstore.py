"""Publish verified UKIs atomically while preserving a separate recovery image."""
import contextlib
import fcntl
import hashlib
import os
import pathlib
import shutil
import tempfile


class InvalidBootImage(RuntimeError):
    pass


def sha256(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(esp, candidate, verify, initialize=False):
    """A failure before replace preserves current; a later failure leaves it valid.

    Recovery is initialized exactly once from the first verified stock image.
    Kernel updates never rotate it implicitly. Recovery replacement requires a
    separate future operation and explicit validation of the new stock image.
    """
    esp, candidate = pathlib.Path(esp), pathlib.Path(candidate)
    if not esp.is_dir() or esp.is_symlink() or candidate.is_symlink():
        raise InvalidBootImage('Unexpected boot image or ESP path')
    linux = esp/'EFI/Linux'
    stage = esp/'.omarchy-staging'
    for p in (esp/'EFI', linux, stage):
        if p.is_symlink():
            raise InvalidBootImage('Boot directory is a symlink')
        p.mkdir(exist_ok=True)
    lock = stage/'publish.lock'
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+b') as locked:
        fcntl.flock(locked, fcntl.LOCK_EX)
        current, recovery = linux/'omarchy-current.efi', linux/'omarchy-recovery.efi'
        for p in (current, recovery):
            if p.is_symlink():
                raise InvalidBootImage('Boot image is a symlink')
            if p.exists():
                verify(p)
        verify(candidate)
        if initialize:
            if current.exists() or recovery.exists():
                raise InvalidBootImage('Existing boot images cannot be reinitialized')
        elif not current.exists() or not recovery.exists():
            raise InvalidBootImage('A verified current and recovery pair is required before updating')
        recovery_before = sha256(recovery) if recovery.exists() else None
        # Temporary files live outside the directory scanned for bootable UKIs.
        with tempfile.TemporaryDirectory(prefix='update-', dir=stage) as tmp:
            staged = pathlib.Path(tmp)/'candidate.efi'
            with candidate.open('rb') as src, staged.open('xb') as dst:
                shutil.copyfileobj(src, dst)
                dst.flush(); os.fsync(dst.fileno())
            verify(staged)
            if initialize:
                staged_recovery = pathlib.Path(tmp)/'recovery.efi'
                with staged.open('rb') as src, staged_recovery.open('xb') as dst:
                    shutil.copyfileobj(src, dst)
                    dst.flush(); os.fsync(dst.fileno())
                verify(staged_recovery)
                os.replace(staged_recovery, recovery)
                sync_dir(linux)
            os.replace(staged, current)
            sync_dir(linux)
        if recovery_before is not None and sha256(recovery) != recovery_before:
            raise InvalidBootImage('Update changed the immutable recovery image')
        verify(current); verify(recovery)
        return {'current_sha256': sha256(current), 'recovery_sha256': sha256(recovery)}
