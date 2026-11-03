import copy
import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'installer'/'disk-protection'))
from policy import Refused, plan, revalidate


def fixture():
    return [
        {'path':'/dev/nvme0n1','model':'Samsung SSD 990 PRO 2TB','serial':'WIN-A','size':2_000_000_000_000,'by_id':'/dev/disk/by-id/wwn-a','partitions':[{'esp':True},{'fstype':'ntfs'}]},
        {'path':'/dev/sda','model':'WDC WDS100T2B0B','serial':'WIN-B','size':1_000_000_000_000,'by_id':'/dev/disk/by-id/wwn-b','partitions':[{'fstype':'BitLocker'}]},
        {'path':'/dev/sdb','model':'CT1000BX500SSD1','serial':'LINUX-C','size':1_000_000_000_000,'by_id':'/dev/disk/by-id/wwn-c','partitions':[]},
    ]


class Safety(unittest.TestCase):
    def test_enumeration_does_not_select_a_different_disk(self):
        d=fixture(); p=plan(d,d[2]['by_id'],'LINUX-C')
        d.reverse(); d[0]['path']='/dev/sda'; d[1]['path']='/dev/sdb'
        self.assertEqual(revalidate(p,d)['serial'],'LINUX-C')

    def test_windows_disks_cannot_be_targets(self):
        for d in fixture()[:2]:
            with self.assertRaises(Refused): plan(fixture(),d['by_id'],d['serial'])

    def test_target_with_windows_or_efi_is_rejected(self):
        for part in ({'fstype':'ntfs'},{'fstype':'BitLocker'},{'esp':True},{'mounted':True}):
            d=fixture(); d[2]['partitions']=[part]
            with self.assertRaises(Refused): plan(d,d[2]['by_id'],'LINUX-C')

    def test_missing_duplicate_and_wrong_identity(self):
        for key,value in (('serial',''),('by_id',''),('serial','WIN-A'),('size',128_000_000_000),('model','Unknown')):
            d=fixture(); d[2][key]=value
            with self.assertRaises(Refused): plan(d,d[2]['by_id'],'LINUX-C')

    def test_mounted_mapped_removable_and_probe_failure(self):
        for flag in ('mounted','holders','removable','probe_error'):
            d=fixture(); d[2][flag]=True
            with self.assertRaises(Refused): plan(d,d[2]['by_id'],'LINUX-C')

    def test_hot_swap_and_plan_edit_fail(self):
        for key,value in (('serial','REPLACEMENT'),('size',999_999_999_999)):
            d=fixture(); p=plan(d,d[2]['by_id'],'LINUX-C'); d[2][key]=value
            with self.assertRaises(Refused): revalidate(p,d)
        d=fixture(); p=plan(d,d[2]['by_id'],'LINUX-C'); p['target']['serial']='EDIT'
        with self.assertRaises(Refused): revalidate(p,d)

    def test_wrong_confirmation_and_missing_protected_disk(self):
        d=fixture()
        with self.assertRaises(Refused): plan(d,d[2]['by_id'],'WIN-A')
        p=plan(d,d[2]['by_id'],'LINUX-C'); d.pop(0)
        with self.assertRaises(Refused): revalidate(p,d)


if __name__=='__main__': unittest.main()
