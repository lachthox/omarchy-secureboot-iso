"""Add an explicit non-installing diagnostic boot entry, preserving originals."""
import pathlib
import re

p = pathlib.Path('work/iso/boot/grub/grub.cfg')
text = p.read_text()
entry = re.search(r"menuentry[^\n]*--id 'archlinux'[^\n]*\{(.*?)\n\}", text, re.S)
assert entry, 'Unsupported GRUB entry'
linux = re.search(r'^\s*linux .*$', entry[1], re.M)
initrd = re.search(r'^\s*initrd .*$', entry[1], re.M)
assert linux and initrd
cmd = linux[0].strip()
cmd = re.sub(r'\bquiet\b|\bsplash\b', '', cmd)
text += "\nmenuentry 'Read-only hardware validation - NO installation' --id 'omarchy-hardware-validation' {\n"
text += cmd + '\n' + initrd[0].strip() + '\n}\n'
cmd += ' console=ttyS0,115200 omarchy_ci=1 systemd.mask=getty@tty1.service systemd.mask=serial-getty@ttyS0.service'
text += "\nmenuentry 'Custom ISO diagnostics - no installation' --id 'omarchy-diagnostics' {\n"
text += cmd + '\n' + initrd[0].strip() + '\n}\n'
text += "set default='omarchy-diagnostics'\nset timeout=5\nset timeout_style=menu\n"
pathlib.Path('work/custom-grub.cfg').write_text(text)
