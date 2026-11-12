"""Synthetic tests: they do not claim real media or channel integrations exist."""
import copy
import json
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone
from jsonschema import Draft202012Validator, FormatChecker

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from validate_packet import validate_packet
NOW=datetime(2026,11,12,13,tzinfo=timezone.utc)

def synthetic_complete():
    p=json.loads((ROOT/'examples'/'gaming_packet_needs_capture.json').read_text())
    p['state']='needs_owner_review'; p['blockers']=[]
    for s in p['sources']: s['access_status']='inspected'
    for c in p['claims']: c['status']='verified'; c['evidence_type']='documented'
    for g in p['games']:
        for kind in ['critic','steam']: g[kind]['status']='verified'
    a=p['media'][0]
    a.update(status='available',local_reference='SYNTHETIC_TEST_ONLY.mp4',duration_seconds=30,
             rights_status='cleared',rights_evidence='SYNTHETIC_TEST_ONLY')
    for v in p['variants']: v.update(technical_capability_status='verified',disclosure_status='reviewed')
    p['approval'].update(evidence_reviewed=True,actual_media_reviewed=True,voice_render_timed=True)
    return p

def codes(p): return {b['code'] for b in validate_packet(p,NOW)['blockers']}

class EditorialContractTests(unittest.TestCase):
    def test_example_is_honestly_blocked(self):
        p=json.loads((ROOT/'examples'/'gaming_packet_needs_capture.json').read_text())
        r=validate_packet(p,NOW)
        self.assertTrue(r['structurally_valid']); self.assertFalse(r['ready_for_owner_review'])
        self.assertIn('MEDIA_REQUIRED',codes(p))
    def test_complete_fixture_reaches_review_not_publication(self):
        r=validate_packet(synthetic_complete(),NOW)
        self.assertTrue(r['ready_for_owner_review'])
        self.assertFalse(r['owner_approved_draft']); self.assertTrue(r['this_validator_does_not_dispatch'])
    def test_spoken_reception_required_in_each_variant(self):
        p=synthetic_complete(); p['segments'][2]['reception_for']=[]
        self.assertIn('MISSING_SPOKEN_RECEPTION',codes(p))
    def test_stale_facts_cannot_pass_after_approval(self):
        p=synthetic_complete(); p['sources'][0]['expires_at']='2026-11-12T12:30:00Z'
        self.assertIn('EXPIRED_SOURCE',codes(p))
    def test_unknown_claim_reference(self):
        p=synthetic_complete(); p['segments'][0]['claim_ids']=['DOES_NOT_EXIST']
        self.assertIn('UNKNOWN_CLAIM',codes(p))
    def test_clip_range_cannot_exceed_source(self):
        p=synthetic_complete(); p['segments'][0]['shots'][0]['source_out']=100
        self.assertIn('SOURCE_RANGE_OVERFLOW',codes(p))
    def test_blocked_score_is_not_a_missing_coverage_exception(self):
        p=synthetic_complete(); p['games'][0]['steam']['status']='blocked'
        self.assertIn('RECEPTION_UNRESOLVED',codes(p))
    def test_silent_gaming_asset_needs_parent(self):
        p=synthetic_complete(); p['variants'][0]['kind']='silent_companion'
        self.assertIn('GAMING_COMPANION_WITHOUT_PARENT',codes(p))
    def test_revision_invalidates_owner_approval(self):
        p=synthetic_complete(); p['approval'].update(owner_approved=True,approved_revision='old',approved_at='2026-11-12T12:30:00Z')
        self.assertIn('APPROVAL_REVISION_MISMATCH',codes(p))
    def test_missing_analytics_stays_null_and_loops_can_exceed_100(self):
        schema=json.loads((ROOT/'schemas'/'analytics.schema.json').read_text())
        p=json.loads((ROOT/'examples'/'analytics_synthetic.json').read_text())
        Draft202012Validator(schema,format_checker=FormatChecker()).validate(p)
        self.assertEqual(p['metrics'][0]['value'],120); self.assertIsNone(p['metrics'][1]['value'])
        self.assertNotIn('completion',p['metrics'][0]['name_native'])
    def test_incomplete_state_and_false_approved_state_block(self):
        p=synthetic_complete(); p['state']='needs_evidence'
        self.assertIn('INCOMPLETE_WORKFLOW_STATE',codes(p))
        p['state']='approved_draft'
        self.assertIn('APPROVED_STATE_WITHOUT_APPROVAL',codes(p))
    def test_verified_reception_requires_a_value(self):
        p=synthetic_complete(); p['games'][0]['steam']['value']=None
        self.assertIn('MISSING_RECEPTION_VALUE',codes(p))
    def test_proposed_evidence_cannot_be_verified(self):
        p=synthetic_complete(); p['claims'][0].update(evidence_type='proposed',source_ids=[])
        self.assertIn('EVIDENCE_STATUS_CONTRADICTION',codes(p))
    def test_nonfinite_timing_and_unknown_duration_block(self):
        p=synthetic_complete(); p['segments'][0]['end']=float('nan')
        self.assertIn('NONFINITE_NUMBER',codes(p))
        p=synthetic_complete(); p['media'][0]['duration_seconds']=None
        self.assertIn('UNKNOWN_MEDIA_DURATION',codes(p))
    def test_omitted_featured_game_cannot_bypass_reception(self):
        p=synthetic_complete(); p['variants'][0]['game_ids']=[]
        self.assertIn('FEATURED_GAME_OMITTED',codes(p))
    def test_unavailable_metric_cannot_be_zero(self):
        schema=json.loads((ROOT/'schemas'/'analytics.schema.json').read_text())
        p=json.loads((ROOT/'examples'/'analytics_synthetic.json').read_text())
        p['metrics'][1]['value']=0
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(p)))
        p['metrics'][1]['value']=None; p['metrics'][0]['value']=None
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(p)))

if __name__=='__main__': unittest.main()
