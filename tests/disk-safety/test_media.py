import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'installer/disk-protection'))
from discovery import installation_medium


class BootMedia(unittest.TestCase):
    def test_writable_usb_is_matched_by_the_boot_filesystem(self):
        usb = {'ro':False,'children':[{'uuid':'BOOT-UUID','fstype':'iso9660','label':'OMARCHY_202610'}]}
        self.assertTrue(installation_medium(usb,'BOOT-UUID'))

    def test_a_label_or_uuid_alone_cannot_hide_a_disk(self):
        for node in ({'uuid':'OTHER','fstype':'iso9660','label':'OMARCHY_202610'},
                     {'uuid':'BOOT-UUID','fstype':'ntfs','label':'OMARCHY_202610'},
                     {'uuid':'BOOT-UUID','fstype':'iso9660','label':'OTHER'}):
            self.assertFalse(installation_medium(node,'BOOT-UUID'))
        self.assertFalse(installation_medium({'uuid':'','fstype':'iso9660','label':'OMARCHY_202610'},''))
