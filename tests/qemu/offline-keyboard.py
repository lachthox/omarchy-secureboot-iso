"""Version-specific VM adaptation: enumerate keymaps without a privileged bus."""
import hashlib
import pathlib

p=pathlib.Path('/usr/share/omarchy-iso/orchestrator/keyboard.py')
original=p.read_bytes()
assert hashlib.sha256(original).hexdigest()=='9fb61f385621ff027300e0187c4f870e25ad64780cef846975caed989cb4ec7c', 'Unexpected keyboard helper'
old='''    result = capture(["localectl", "--no-pager", "list-keymaps"])
    if result.returncode != 0:
        detail = result.stderr.strip() or "localectl returned an error"
        raise RuntimeError(f"Unable to list keyboard layouts: {detail}")
    if language.lower() not in {layout.lower() for layout in result.stdout.splitlines()}:
'''
new='''    # Custom ISO sandbox adaptation: enumerate trusted local keymap files.
    layouts = {p.name.split(".map", 1)[0].lower()
               for p in Path("/usr/share/kbd/keymaps").rglob("*.map*") if p.is_file()}
    if not layouts:
        raise RuntimeError("No local keyboard layouts found")
    if language.lower() not in layouts:
'''
text=original.decode()
assert text.count(old)==1
text=text.replace(old,new)
compile(text,str(p),'exec')
p.write_text(text)
print('OFFLINE_KEYBOARD_ADAPTATION_APPLIED sha256='+hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
