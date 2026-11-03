"""Keep archinstall descendants in the device cgroup instead of delegating to PID 1."""
import hashlib
import pathlib

p=pathlib.Path('/usr/lib/python3.14/site-packages/archinstall/lib/installer.py')
data=p.read_bytes()
assert hashlib.sha256(data).hexdigest()=='8a891c129a4baf266f60c0fe9cbbcc38b22c4e895c6708b3fabef0aea7abdea3'
text=data.decode()
assert text.count('arch-chroot -S ')==2
assert text.count("['arch-chroot', '-S',")==1
text=text.replace('arch-chroot -S ','arch-chroot ').replace("['arch-chroot', '-S',","['arch-chroot',")
compile(text,str(p),'exec')
p.write_text(text)
print('CLASSIC_CHROOT_ADAPTATION_APPLIED sha256='+hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
