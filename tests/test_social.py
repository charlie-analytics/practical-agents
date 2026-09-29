import json
import unittest
from pathlib import Path
from agentkit.__main__ import demo
from agentkit.tools import Tools

ROOT=Path(__file__).resolve().parents[1]/'examples'


class SocialTests(unittest.TestCase):
    def test_missing_context_requires_revision(self):
        r=demo('social-editor',ROOT)['result']
        self.assertEqual(r['first_draft']['status'],'revise_or_ask')
        self.assertIn('missing_required_context:s2',r['first_draft']['issues'])
        self.assertEqual(r['revised_draft']['status'],'ready_for_human_review')
        self.assertFalse(r['revised_draft']['publish_performed'])

    def test_same_clip_rejected_for_wrong_account(self):
        r=demo('social-editor',ROOT)['result']['different_account']
        self.assertIn('topic_not_allowed_for_account',r['issues'])

    def test_unknown_citation_does_not_pass(self):
        draft={'account_id':'research-linkedin','start_second':0,'end_second':22,'caption':'A test','topic':'research','evidence_ids':['invented']}
        r=Tools(ROOT).review_social_draft('clip-manifest.json','social-accounts.json',json.dumps(draft))
        self.assertIn('unknown_evidence:invented',r['issues'])

    def test_context_expands_around_quote(self):
        r=Tools(ROOT).context_window('clip-manifest.json',0,7,15)
        self.assertEqual([s['id'] for s in r['segments']],['s1','s2','s3'])

    def test_dedupe_changes_when_caption_changes(self):
        r=demo('social-editor',ROOT)['result']
        self.assertNotEqual(r['first_draft']['dedupe_key'],r['revised_draft']['dedupe_key'])
