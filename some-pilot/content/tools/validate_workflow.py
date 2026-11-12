"""Validate a complete backend draft and compute dispatch authorization; no API calls.

Exit 0: authorized destinations exist. Exit 2: blocked, synthetic, or no work remains.
Exit 3: malformed input. See DATA_CONTRACT.md for the protected-field trust boundary.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from validate_packet import moment

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = re.compile(r"synthetic|fixture|placeholder|example|replace[_ -]?me|\.invalid|<[^>]+>", re.I)


def payload_hash(payload):
    """Hash exactly these UTF-8 JSON bytes; persist the same bytes in the backend."""
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def idempotency_key(story_id, revision, destination, digest):
    raw = '\0'.join([story_id, revision, destination['id'],
                     destination['account_id'] or '', digest]).encode('utf-8')
    return 'pp_' + hashlib.sha256(raw).hexdigest()


def validate_workflow(record, config, artifact_root, now=None):
    """Pure local gate. All approval/capability/review fields must be backend-owned."""
    now = now or datetime.now(timezone.utc)
    schema = json.loads((ROOT / 'schemas/workflow.schema.json').read_text())
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(record))
    base = {'this_validator_does_not_dispatch': True, 'structurally_valid': not errors,
            'draft_complete': False, 'owner_approval_valid': False,
            'eligible_destination_ids': [], 'dispatch_authorized': False,
            'dispatch_destination_ids': [], 'destination_blockers': {}}
    if errors:
        return dict(base, blockers=[{'code': 'SCHEMA', 'detail':
                    '.'.join(map(str, e.absolute_path)) + ': ' + e.message} for e in errors])
    blockers = []
    def fail(code, detail):
        item = {'code': code, 'detail': detail}
        if item not in blockers:
            blockers.append(item)
    payload, backend, approval = record['payload'], record['backend'], record['approval']
    try:
        digest = payload_hash(payload)
    except ValueError as error:
        return dict(base, blockers=[{'code': 'NONFINITE_NUMBER', 'detail': str(error)}])
    base['payload_sha256'] = digest
    artifacts = {a['id']: a for a in payload['artifacts']}
    destinations = {d['id']: d for d in payload['destinations']}
    deliveries = {d['destination_id']: d for d in record['deliveries']}
    for name, mapping, rows in [('artifact', artifacts, payload['artifacts']),
                                ('destination', destinations, payload['destinations']),
                                ('delivery', deliveries, record['deliveries'])]:
        if len(mapping) != len(rows):
            fail('DUPLICATE_ID', name)
    if set(deliveries) != set(destinations):
        fail('DELIVERY_SET_MISMATCH', 'Every selected destination needs exactly one delivery record.')
    root = Path(artifact_root).resolve()
    for asset in artifacts.values():
        if asset['status'] != 'complete' or not asset['storage_path'] or not asset['sha256']:
            fail('ARTIFACT_INCOMPLETE', asset['id'])
            continue
        path = (root / asset['storage_path']).resolve()
        if Path(asset['storage_path']).is_absolute() or not path.is_relative_to(root):
            fail('ARTIFACT_OUTSIDE_ROOT', asset['id'])
            continue
        if not path.is_file():
            fail('ARTIFACT_MISSING', asset['id'])
            continue
        hasher = hashlib.sha256()
        actual_bytes = 0
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                actual_bytes += len(chunk)
                hasher.update(chunk)
        if not actual_bytes or actual_bytes != asset['bytes'] or hasher.hexdigest() != asset['sha256']:
            fail('ARTIFACT_CHANGED', asset['id'])
    def require_asset(aid, kind):
        asset = artifacts.get(aid)
        if not asset or asset['kind'] != kind:
            fail('REQUIRED_DELIVERABLE_MISSING', kind + ': ' + aid)
            return None
        prefixes = {'script': ('text/',), 'thumbnail': ('image/',), 'narration': ('audio/',),
                    'video': ('video/',), 'captions': ('text/vtt', 'application/x-subrip', 'text/plain')}[kind]
        if not asset['content_type'].startswith(prefixes):
            fail('ARTIFACT_TYPE_MISMATCH', aid)
        return asset
    require_asset(payload['script_artifact_id'], 'script')
    narration = require_asset(payload['narration_artifact_id'], 'narration')
    def check_voice(asset):
        if not asset:
            return
        if asset['provider'] != 'elevenlabs' or not asset['voice_id']:
            fail('ELEVENLABS_VOICE_REQUIRED', asset['id'])
        profile = config.get('voice_profiles', {}).get(payload['voice_profile'], {})
        if not profile.get('voice_id') or asset['voice_id'] != profile['voice_id']:
            fail('VOICE_PROFILE_MISMATCH', payload['voice_profile'])
    check_voice(narration)
    accounts = []
    for dest in destinations.values():
        require_asset(dest['script_artifact_id'], 'script')
        check_voice(require_asset(dest['narration_artifact_id'], 'narration'))
        require_asset(dest['captions_artifact_id'], 'captions')
        require_asset(dest['video_artifact_id'], 'video')
        require_asset(dest['thumbnail_artifact_id'], 'thumbnail')
        if not dest['account_id']:
            fail('DESTINATION_ACCOUNT_MISSING', dest['id'])
        accounts.append({'destination_id': dest['id'], 'account_id': dest['account_id']})
        if not dest['title'].strip() or not dest['caption'].strip() or any(not h.strip() for h in dest['hashtags']):
            fail('METADATA_INCOMPLETE', dest['id'])
    if not backend['draft_id'] or not backend['saved_at']:
        fail('BACKEND_DRAFT_NOT_SAVED', record['story_id'])
    if backend['revision'] != payload['revision'] or backend['persisted_payload_sha256'] != digest:
        fail('BACKEND_REVISION_OR_HASH_MISMATCH', payload['revision'])
    if backend['saved_at'] and moment(backend['saved_at']) > now:
        fail('FUTURE_BACKEND_TIMESTAMP', backend['saved_at'])
    if backend['state'] == 'building':
        fail('BACKEND_DRAFT_INCOMPLETE', backend['state'])
    for field in ['editorial_gate_passed', 'actual_media_review_passed']:
        if not record['preflight'][field]:
            fail('TRUSTED_REVIEW_MISSING', field)
    base['draft_complete'] = not blockers
    draft_blocker_count = len(blockers)
    publishing = config.get('publishing', {})
    if backend['state'] not in ['approved', 'dispatching', 'partially_published']:
        fail('BACKEND_NOT_APPROVED_FOR_DISPATCH', backend['state'])
    if approval['decision'] != 'approved' or backend['state'] == 'rejected':
        fail('OWNER_APPROVAL_REQUIRED', approval['decision'])
    if not publishing.get('owner_id') or approval['reviewer_id'] != publishing['owner_id']:
        fail('OWNER_ID_MISMATCH', 'Approval must come from the configured Sebastian account.')
    if approval['revision'] != payload['revision'] or approval['payload_sha256'] != digest:
        fail('APPROVAL_INVALIDATED', 'Revision or immutable payload changed; obtain a new owner decision.')
    if sorted(approval['destination_accounts'], key=lambda x: x['destination_id']) != sorted(accounts, key=lambda x: x['destination_id']):
        fail('APPROVAL_DESTINATIONS_MISMATCH', 'Approval must bind every selected destination and account ID.')
    if not approval['backend_event_id'] or not approval['decided_at']:
        fail('APPROVAL_EVENT_MISSING', 'Authenticated backend decision required.')
    elif moment(approval['decided_at']) > now or (backend['saved_at'] and moment(approval['decided_at']) < moment(backend['saved_at'])):
        fail('APPROVAL_TIME_INVALID', approval['decided_at'])
    base['owner_approval_valid'] = len(blockers) == draft_blocker_count
    if not publishing.get('enabled') or publishing.get('mode') != 'automatic_after_owner_approval':
        fail('AUTOMATIC_DISPATCH_NOT_CONFIGURED', 'Target mode must permit automatic publishing after owner approval.')
    refresh = record['preflight']['source_refresh']
    if refresh['status'] != 'passed' or refresh['payload_sha256'] != digest or not refresh['evidence_reference']:
        fail('SOURCE_REFRESH_REQUIRED', 'Recheck live facts against this exact approved payload.')
    if not refresh['checked_at'] or not refresh['valid_until'] or moment(refresh['checked_at']) > now or moment(refresh['valid_until']) <= now:
        fail('SOURCE_REFRESH_EXPIRED', 'A final source check with a current validity window is required.')
    for dest_id, dest in destinations.items():
        delivery = deliveries.get(dest_id)
        reasons = []
        def blocked(code):
            if code not in reasons:
                reasons.append(code)
        options = dest['publication_options']
        if options['timing'] == 'scheduled' and moment(options['publish_at']) > now:
            blocked('SCHEDULE_NOT_DUE')
        if not delivery:
            blocked('DELIVERY_MISSING')
        else:
            if delivery['payload_sha256'] != digest or delivery['idempotency_key'] != idempotency_key(record['story_id'], payload['revision'], dest, digest):
                blocked('DELIVERY_BINDING_MISMATCH')
            status = delivery['status']
            reconciliation = delivery['reconciliation']
            if status == 'published' or delivery['platform_post_id'] or reconciliation['status'] == 'confirmed_published':
                blocked('ALREADY_PUBLISHED_NEVER_REUPLOAD')
            elif status == 'in_progress':
                blocked('ATTEMPT_IN_PROGRESS')
            elif status == 'unknown':
                blocked('UNKNOWN_RESULT_RECONCILE_FIRST')
            elif status == 'pending' and delivery['attempt_count'] != 0:
                blocked('RETRY_MUST_BE_FAILED_DESTINATION')
            elif status == 'failed':
                if delivery['attempt_count'] < 1 or not delivery['last_attempt_at'] or not delivery['failure_retryable']:
                    blocked('FAILURE_NOT_RETRYABLE')
                if reconciliation['status'] == 'needs_check':
                    blocked('UNKNOWN_RESULT_RECONCILE_FIRST')
                if reconciliation['status'] == 'confirmed_not_published':
                    if not reconciliation['checked_at'] or not reconciliation['receipt_reference'] or (delivery['last_attempt_at'] and moment(reconciliation['checked_at']) < moment(delivery['last_attempt_at'])) or (reconciliation['checked_at'] and moment(reconciliation['checked_at']) > now):
                        blocked('RECONCILIATION_EVIDENCE_MISSING')
            connection = publishing.get('live_connections', {}).get(dest['platform'], {})
            if connection.get('status') != 'verified' or not connection.get('connection_reference') or connection.get('account_id') != dest['account_id']:
                blocked('DESTINATION_CAPABILITY_UNCONFIGURED')
            checked, valid_until = connection.get('capability_checked_at'), connection.get('capability_valid_until')
            try:
                if not checked or not valid_until or moment(checked) > now or moment(valid_until) <= now:
                    blocked('DESTINATION_CAPABILITY_EXPIRED')
            except (ValueError, TypeError):
                blocked('DESTINATION_CAPABILITY_EXPIRED')
        if reasons:
            base['destination_blockers'][dest_id] = reasons
        elif not blockers:
            base['eligible_destination_ids'].append(dest_id)
    # Test fixtures can exercise the entire contract but never produce dispatch IDs.
    if record['is_synthetic']:
        fail('SYNTHETIC_FIXTURE_NO_DISPATCH', 'Synthetic approval and capability records are not live authorization.')
    protected_strings = [record['story_id'], backend['draft_id'], approval['backend_event_id'], approval['reviewer_id']]
    protected_strings += [d['account_id'] for d in destinations.values()]
    protected_strings += [a['storage_path'] for a in artifacts.values()]
    protected_strings += [a['voice_id'] for a in artifacts.values()]
    protected_strings += [c.get('connection_reference') for c in publishing.get('live_connections', {}).values()]
    protected_strings += [refresh['evidence_reference']]
    if any(value and PLACEHOLDER.search(value) for value in protected_strings):
        fail('PLACEHOLDER_NO_DISPATCH', 'Replace demonstration identities and assets through trusted integrations.')
    base['dispatch_authorized'] = not blockers and bool(base['eligible_destination_ids'])
    if base['dispatch_authorized']:
        base['dispatch_destination_ids'] = list(base['eligible_destination_ids'])
    base['blockers'] = blockers
    base['limitation'] = 'Local contract checks only. No API calls, media decoding, credential checks, or authenticated owner event verification are implemented here.'
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workflow')
    parser.add_argument('--config', default=str(ROOT / 'config.json'))
    parser.add_argument('--artifact-root', required=True)
    parser.add_argument('--now', help='ISO timestamp override for reproducible synthetic tests only')
    args = parser.parse_args()
    try:
        def reject_constant(value):
            raise ValueError('Nonstandard JSON number: ' + value)
        record = json.loads(Path(args.workflow).read_text(), parse_constant=reject_constant)
        config = json.loads(Path(args.config).read_text(), parse_constant=reject_constant)
        result = validate_workflow(record, config, args.artifact_root, moment(args.now) if args.now else None)
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({'error': str(error), 'dispatch_authorized': False, 'this_validator_does_not_dispatch': True}))
        return 3
    print(json.dumps(result, indent=2))
    return 3 if not result['structurally_valid'] else (0 if result['dispatch_authorized'] else 2)


if __name__ == '__main__':
    raise SystemExit(main())
