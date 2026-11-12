"""Synthetic lifecycle tests only: no real voices, media, approvals or API calls.

Temporary bytes test artifact existence and integrity, not audiovisual validity.
All apparent owner/capability events below are fictional test inputs.
"""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from validate_workflow import validate_workflow, payload_hash, idempotency_key

NOW = datetime(2026, 11, 12, 13, tzinfo=timezone.utc)
CHECKED = '2026-11-12T12:00:00Z'
APPROVED = '2026-11-12T12:30:00Z'
FRESH = '2026-11-12T14:00:00Z'


def synthetic_approved(root):
    """A complete contract fixture; never a real approved publishing package."""
    config = json.loads((ROOT / 'config.json').read_text())
    config['publishing']['owner_id'] = 'SYNTHETIC-Sebastian'
    config['voice_profiles']['gaming']['voice_id'] = 'SYNTHETIC-voice-gaming'
    artifacts = []
    for aid, kind, mime in [('script', 'script', 'text/plain'),
                            ('cover', 'thumbnail', 'image/png'),
                            ('voice', 'narration', 'audio/wav'),
                            ('video', 'video', 'video/mp4'),
                            ('captions', 'captions', 'text/vtt')]:
        raw = ('SYNTHETIC UNIT TEST BYTES: ' + aid).encode()
        path = 'SYNTHETIC-' + aid + '.bin'
        (Path(root) / path).write_bytes(raw)
        artifacts.append({'id': aid, 'kind': kind, 'storage_path': path,
                          'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                          'content_type': mime, 'status': 'complete',
                          'provider': 'elevenlabs' if aid == 'voice' else None,
                          'voice_id': 'SYNTHETIC-voice-gaming' if aid == 'voice' else None})
    destinations = []
    for platform in ['facebook', 'instagram', 'youtube', 'tiktok']:
        account = 'SYNTHETIC-account-' + platform
        destinations.append({'id': platform, 'platform': platform, 'account_id': account,
            'variant_id': platform + '-vertical', 'video_artifact_id': 'video',
            'script_artifact_id': 'script', 'narration_artifact_id': 'voice',
            'captions_artifact_id': 'captions', 'thumbnail_artifact_id': 'cover', 'title': 'Synthetic workflow title',
            'caption': 'Fictional contract test; never publish.', 'hashtags': ['#SyntheticTest'],
            'publication_options': {'timing': 'immediate', 'publish_at': None, 'visibility': 'public', 'cover_mode': 'adapter_verified'}})
        config['publishing']['live_connections'][platform] = {
            'status': 'verified', 'account_id': account,
            'connection_reference': 'SYNTHETIC-connection-' + platform,
            'capability_checked_at': CHECKED, 'capability_valid_until': FRESH}
    payload = {'bible_version': '1.1.0', 'revision': 'synthetic-r1', 'lane': 'gaming',
               'voice_profile': 'gaming', 'editorial_packet_sha256': 'a' * 64, 'script_artifact_id': 'script',
               'narration_artifact_id': 'voice', 'artifacts': artifacts,
               'destinations': destinations}
    digest = payload_hash(payload)
    record = {'schema_version': '1.1.0', 'story_id': 'SYNTHETIC-STORY', 'is_synthetic': True,
        'payload': payload,
        'backend': {'draft_id': 'SYNTHETIC-DRAFT', 'revision': payload['revision'],
                    'persisted_payload_sha256': digest, 'saved_at': CHECKED, 'state': 'approved'},
        'approval': {'decision': 'approved', 'reviewer_id': 'SYNTHETIC-Sebastian',
                     'decided_at': APPROVED, 'revision': payload['revision'], 'payload_sha256': digest,
                     'destination_accounts': [{'destination_id': d['id'], 'account_id': d['account_id']} for d in destinations],
                     'backend_event_id': 'SYNTHETIC-APPROVAL-EVENT'},
        'preflight': {'editorial_gate_passed': True, 'actual_media_review_passed': True,
                      'source_refresh': {'status': 'passed', 'checked_at': APPROVED, 'valid_until': FRESH,
                                         'payload_sha256': digest, 'evidence_reference': 'SYNTHETIC-source-check'}},
        'deliveries': [{'destination_id': d['id'], 'payload_sha256': digest,
                       'idempotency_key': idempotency_key('SYNTHETIC-STORY', payload['revision'], d, digest),
                       'status': 'pending', 'attempt_count': 0, 'last_attempt_at': None,
                       'failure_retryable': False, 'platform_post_id': None,
                       'reconciliation': {'status': 'not_required', 'checked_at': None, 'receipt_reference': None}}
                      for d in destinations]}
    return record, config


class ProductionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.record, self.config = synthetic_approved(self.temp.name)

    def result(self):
        return validate_workflow(self.record, self.config, self.temp.name, NOW)

    def codes(self):
        return {b['code'] for b in self.result()['blockers']}

    def test_target_config_enables_automatic_approved_dispatch_but_no_live_connections(self):
        c = json.loads((ROOT / 'config.json').read_text())
        self.assertEqual(c['publish_mode'], 'automatic_after_owner_approval')
        self.assertTrue(c['publishing']['enabled'])
        self.assertEqual(set(c['publishing']['default_destinations']), {'facebook', 'instagram', 'youtube', 'tiktok'})
        self.assertTrue(all(x['status'] == 'unconfigured' and x['account_id'] is None for x in c['publishing']['live_connections'].values()))

    def test_complete_synthetic_approval_exercises_four_destinations_but_never_dispatches(self):
        r = self.result()
        self.assertTrue(r['draft_complete'])
        self.assertTrue(r['owner_approval_valid'])
        self.assertEqual(len(r['eligible_destination_ids']), 4)
        self.assertFalse(r['dispatch_authorized'])
        self.assertEqual(r['dispatch_destination_ids'], [])
        self.assertIn('SYNTHETIC_FIXTURE_NO_DISPATCH', self.codes())
        self.assertTrue(r['this_validator_does_not_dispatch'])

    def test_every_actual_deliverable_must_exist(self):
        for asset in self.record['payload']['artifacts']:
            with self.subTest(kind=asset['kind']):
                path = Path(self.temp.name) / asset['storage_path']
                original = path.read_bytes()
                path.unlink()
                self.assertIn('ARTIFACT_MISSING', self.codes())
                self.assertFalse(self.result()['draft_complete'])
                path.write_bytes(original)

    def test_changed_asset_bytes_invalidate_the_package(self):
        (Path(self.temp.name) / self.record['payload']['artifacts'][1]['storage_path']).write_bytes(b'changed')
        self.assertIn('ARTIFACT_CHANGED', self.codes())

    def test_narration_requires_elevenlabs_and_the_selected_voice(self):
        voice = self.record['payload']['artifacts'][2]
        voice['provider'] = 'different-provider'
        self.assertIn('ELEVENLABS_VOICE_REQUIRED', self.codes())
        voice['provider'] = 'elevenlabs'
        voice['voice_id'] = 'different-voice'
        self.assertIn('VOICE_PROFILE_MISMATCH', self.codes())

    def test_title_caption_and_hashtags_are_required(self):
        dest = self.record['payload']['destinations'][0]
        for key, empty in [('title', ''), ('caption', ''), ('hashtags', [])]:
            with self.subTest(field=key):
                original = dest[key]
                dest[key] = empty
                self.assertIn('SCHEMA', self.codes())
                dest[key] = original

    def test_backend_must_persist_the_exact_revision_and_payload(self):
        self.record['backend']['persisted_payload_sha256'] = '0' * 64
        self.assertIn('BACKEND_REVISION_OR_HASH_MISMATCH', self.codes())

    def test_pending_owner_decision_blocks_all_destinations(self):
        self.record['approval']['decision'] = 'pending'
        self.assertIn('OWNER_APPROVAL_REQUIRED', self.codes())
        self.assertEqual(self.result()['eligible_destination_ids'], [])

    def test_rejected_backend_draft_cannot_publish(self):
        self.record['backend']['state'] = 'rejected'
        self.record['approval']['decision'] = 'rejected'
        self.assertIn('OWNER_APPROVAL_REQUIRED', self.codes())

    def test_any_payload_edit_invalidates_approval_even_without_revision_bump(self):
        self.record['payload']['destinations'][0]['title'] = 'Changed after approval'
        self.assertIn('APPROVAL_INVALIDATED', self.codes())

    def test_revision_change_requires_new_approval(self):
        self.record['payload']['revision'] = 'synthetic-r2'
        self.assertIn('APPROVAL_INVALIDATED', self.codes())

    def test_account_selection_is_bound_to_owner_decision(self):
        self.record['approval']['destination_accounts'][0]['account_id'] = 'SYNTHETIC-other-account'
        self.assertIn('APPROVAL_DESTINATIONS_MISMATCH', self.codes())

    def test_only_configured_owner_can_approve(self):
        self.record['approval']['reviewer_id'] = 'SYNTHETIC-other-person'
        self.assertIn('OWNER_ID_MISMATCH', self.codes())

    def test_expired_source_refresh_blocks_approved_payload(self):
        self.record['preflight']['source_refresh']['valid_until'] = CHECKED
        self.assertIn('SOURCE_REFRESH_EXPIRED', self.codes())

    def test_changed_source_facts_require_rework(self):
        self.record['preflight']['source_refresh']['status'] = 'changed'
        self.assertIn('SOURCE_REFRESH_REQUIRED', self.codes())

    def test_unconfigured_destination_blocks_only_its_own_dispatch(self):
        self.config['publishing']['live_connections']['tiktok']['status'] = 'unconfigured'
        r = self.result()
        self.assertNotIn('tiktok', r['eligible_destination_ids'])
        self.assertEqual(len(r['eligible_destination_ids']), 3)
        self.assertIn('DESTINATION_CAPABILITY_UNCONFIGURED', r['destination_blockers']['tiktok'])

    def test_expired_capability_is_rechecked_before_dispatch(self):
        self.config['publishing']['live_connections']['instagram']['capability_valid_until'] = CHECKED
        self.assertIn('DESTINATION_CAPABILITY_EXPIRED', self.result()['destination_blockers']['instagram'])

    def test_partial_success_retries_only_failed_destination(self):
        fb, ig, yt, tt = self.record['deliveries']
        fb.update(status='published', platform_post_id='SYNTHETIC-post-fb', attempt_count=1, last_attempt_at=APPROVED)
        ig.update(status='failed', attempt_count=1, last_attempt_at=APPROVED, failure_retryable=True)
        yt.update(status='published', platform_post_id='SYNTHETIC-post-yt', attempt_count=1, last_attempt_at=APPROVED)
        tt.update(status='in_progress', attempt_count=1, last_attempt_at=APPROVED)
        self.assertEqual(self.result()['eligible_destination_ids'], ['instagram'])

    def test_unknown_outcome_requires_reconciliation_receipt_before_retry(self):
        d = self.record['deliveries'][0]
        d.update(status='unknown', attempt_count=1, last_attempt_at=APPROVED, failure_retryable=True)
        d['reconciliation']['status'] = 'needs_check'
        self.assertIn('UNKNOWN_RESULT_RECONCILE_FIRST', self.result()['destination_blockers']['facebook'])
        d['status'] = 'failed'
        d['reconciliation']['status'] = 'confirmed_not_published'
        self.assertIn('RECONCILIATION_EVIDENCE_MISSING', self.result()['destination_blockers']['facebook'])
        d['reconciliation'].update(checked_at='2026-11-12T12:45:00Z', receipt_reference='SYNTHETIC-reconciliation')
        self.assertIn('facebook', self.result()['eligible_destination_ids'])

    def test_recorded_post_id_prevents_reupload_even_if_state_is_wrong(self):
        d = self.record['deliveries'][0]
        d.update(status='failed', platform_post_id='SYNTHETIC-post', attempt_count=1, last_attempt_at=APPROVED, failure_retryable=True)
        self.assertIn('ALREADY_PUBLISHED_NEVER_REUPLOAD', self.result()['destination_blockers']['facebook'])

    def test_pending_with_prior_attempt_is_not_a_new_upload(self):
        self.record['deliveries'][0]['attempt_count'] = 1
        self.assertIn('RETRY_MUST_BE_FAILED_DESTINATION', self.result()['destination_blockers']['facebook'])

    def test_permanent_failure_is_not_retried(self):
        self.record['deliveries'][0].update(status='failed', attempt_count=1, last_attempt_at=APPROVED)
        self.assertIn('FAILURE_NOT_RETRYABLE', self.result()['destination_blockers']['facebook'])

    def test_idempotency_key_is_bound_to_selected_payload_and_account(self):
        self.record['deliveries'][0]['idempotency_key'] = 'SYNTHETIC-wrong-key'
        self.assertIn('DELIVERY_BINDING_MISMATCH', self.result()['destination_blockers']['facebook'])

    def test_clearing_fixture_flag_does_not_make_placeholders_dispatchable(self):
        self.record['is_synthetic'] = False
        self.assertIn('PLACEHOLDER_NO_DISPATCH', self.codes())
        self.assertFalse(self.result()['dispatch_authorized'])

    def test_all_published_means_no_new_upload_work(self):
        for d in self.record['deliveries']:
            d.update(status='published', platform_post_id='SYNTHETIC-post-' + d['destination_id'])
        self.assertEqual(self.result()['eligible_destination_ids'], [])
        self.assertFalse(self.result()['dispatch_authorized'])

    def test_declared_files_do_not_replace_actual_media_review(self):
        self.record['preflight']['actual_media_review_passed'] = False
        self.assertIn('TRUSTED_REVIEW_MISSING', self.codes())

    def test_artifact_paths_cannot_escape_the_package_root(self):
        self.record['payload']['artifacts'][0]['storage_path'] = '../outside.txt'
        self.assertIn('ARTIFACT_OUTSIDE_ROOT', self.codes())

    def test_subtitle_artifact_is_required_beyond_the_social_caption(self):
        self.record['payload']['artifacts'] = [a for a in self.record['payload']['artifacts'] if a['kind'] != 'captions']
        self.assertTrue(self.record['payload']['destinations'][0]['caption'])
        self.assertIn('REQUIRED_DELIVERABLE_MISSING', self.codes())
        self.assertFalse(self.result()['draft_complete'])

    def test_backend_review_state_overrides_an_old_approved_event(self):
        for state in ['needs_owner_review', 'building', 'rejected', 'published']:
            with self.subTest(state=state):
                self.record['backend']['state'] = state
                self.assertIn('BACKEND_NOT_APPROVED_FOR_DISPATCH', self.codes())
                self.assertFalse(self.result()['owner_approval_valid'])
                self.assertEqual(self.result()['eligible_destination_ids'], [])

    def test_reviewed_schedule_is_required_and_never_released_early(self):
        dest = self.record['payload']['destinations'][0]
        options = dest['publication_options']
        del options['timing']
        self.assertIn('SCHEMA', self.codes())
        options.update(timing='scheduled', publish_at='2026-11-15T13:00:00Z')
        def reseal_fictional_approval():
            digest = payload_hash(self.record['payload'])
            self.record['backend']['persisted_payload_sha256'] = digest
            self.record['approval']['payload_sha256'] = digest
            self.record['preflight']['source_refresh']['payload_sha256'] = digest
            for d, delivery in zip(self.record['payload']['destinations'], self.record['deliveries']):
                delivery['payload_sha256'] = digest
                delivery['idempotency_key'] = idempotency_key(self.record['story_id'], self.record['payload']['revision'], d, digest)
        reseal_fictional_approval()
        self.assertTrue(self.result()['draft_complete'])
        self.assertTrue(self.result()['owner_approval_valid'])
        self.assertIn('SCHEDULE_NOT_DUE', self.result()['destination_blockers']['facebook'])
        self.assertNotIn('facebook', self.result()['eligible_destination_ids'])
        options['publish_at'] = '2026-11-12T13:00:00Z'
        reseal_fictional_approval()
        self.assertIn('facebook', self.result()['eligible_destination_ids'])


if __name__ == '__main__':
    unittest.main()
