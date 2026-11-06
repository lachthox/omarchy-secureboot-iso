"""Strict, idempotent adaptations required by the actual restricted writer."""
import hashlib
import pathlib


def replace(path, expected, replacements):
    p = pathlib.Path(path)
    data = p.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError('Unsupported upstream source: '+str(p))
    text = data.decode()
    for old, new, count in replacements:
        if text.count(old) != count:
            raise RuntimeError('Unsupported upstream operation: '+str(p))
        text = text.replace(old, new)
    compile(text, str(p), 'exec')
    p.write_text(text)


def apply():
    replace('/usr/lib/python3.14/site-packages/archinstall/lib/installer.py',
            '8a891c129a4baf266f60c0fe9cbbcc38b22c4e895c6708b3fabef0aea7abdea3', [
                ('arch-chroot -S ', 'arch-chroot ', 2),
                ("['arch-chroot', '-S',", "['arch-chroot',", 1)])
    replace('/usr/share/omarchy-iso/orchestrator/keyboard.py',
            '9fb61f385621ff027300e0187c4f870e25ad64780cef846975caed989cb4ec7c', [(
                '''    result = capture(["localectl", "--no-pager", "list-keymaps"])
    if result.returncode != 0:
        detail = result.stderr.strip() or "localectl returned an error"
        raise RuntimeError(f"Unable to list keyboard layouts: {detail}")
    if language.lower() not in {layout.lower() for layout in result.stdout.splitlines()}:
''', '''    layouts = {p.name.split(".map", 1)[0].lower()
               for p in Path("/usr/share/kbd/keymaps").rglob("*.map*") if p.is_file()}
    if not layouts:
        raise RuntimeError("No local keyboard layouts found")
    if language.lower() not in layouts:
''', 1)])
    # A target-local fallback loader is sufficient. The writer must never
    # register, delete or reorder firmware boot entries on a dual-boot machine.
    replace('/usr/share/omarchy-iso/orchestrator/phases_impl.py',
            'c43a393c99b90d458e85ad91de2ddc31ba687960844d4314709a386229767e34', [(
                '''            f"cryptdevice=UUID={storage['luks_uuid']}:omarchy_root "
''',
                '''            f"rd.luks.name={storage['luks_uuid']}=omarchy_root "
            f"cryptdevice=UUID={storage['luks_uuid']}:omarchy_root "
''', 1), (
                '    _register_limine_efi_entry(disk, part, loader, pre_state=pre_state)',
                '    # Guarded installation: firmware registration is deliberately omitted.', 1), (
                '''        post = _read_efibootmgr()
        if not _find_label_entries(post["entries"], "Limine"):
            raise RuntimeError("no 'Limine' entry registered in efibootmgr")''',
                '''        fallback = esp_mount / "EFI" / "BOOT" / "BOOTX64.EFI"
        if not fallback.is_file() or not fallback.stat().st_size:
            raise RuntimeError("Target-local fallback EFI loader is missing")''', 1)])
