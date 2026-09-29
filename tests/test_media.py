import unittest
from agentkit.media import validate_edit


class EditTests(unittest.TestCase):
    def setUp(self): self.assets=[{'id':'asset-0','duration_seconds':30},{'id':'asset-1','duration_seconds':10}]

    def test_multi_source_edit(self):
        r=validate_edit({'canvas':'portrait','clips':[{'asset_id':'asset-0','start':0,'end':10},{'asset_id':'asset-1','start':2,'end':7,'keep_audio':False}]},self.assets)
        self.assertEqual(r['duration_seconds'],15)
        self.assertEqual(len(r['asset_ids']),2)

    def test_invalid_timings(self):
        for start,end in [(-1,5),(1,31),(5,2),(0,float('nan')),(0,float('inf'))]:
            with self.assertRaises(ValueError): validate_edit({'canvas':'portrait','clips':[{'asset_id':'asset-0','start':start,'end':end}]},self.assets)

    def test_unknown_asset(self):
        with self.assertRaises(ValueError): validate_edit({'canvas':'portrait','clips':[{'asset_id':'made-up','start':0,'end':5}]},self.assets)

    def test_bad_canvas(self):
        with self.assertRaises(ValueError): validate_edit({'canvas':'sideways','clips':[{'asset_id':'asset-0','start':0,'end':5}]},self.assets)

    def test_crop_rejects_unbounded_or_non_numeric_focus(self):
        for value in [float('nan'), float('inf'), -0.1, 1.1, True, '0.5']:
            with self.assertRaises(ValueError):
                validate_edit({'canvas':'feed','clips':[{'asset_id':'asset-0','start':0,'end':5,'fit':'cover','focus_x':value}]},self.assets)
