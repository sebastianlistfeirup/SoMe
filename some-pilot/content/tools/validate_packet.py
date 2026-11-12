"""Structural and deterministic editorial checks; never a factual or media audit.

Run from the kit root: python tools/validate_packet.py examples/gaming_packet_needs_capture.json
Exit 0: structurally valid and ready for owner review. Exit 2: expected draft blockers.
Exit 3: schema or input failure. This editorial gate does not dispatch. Use validate_workflow.py for the separate approval and dispatch contract.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]

def moment(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)

def validate_packet(packet, now=None):
    now = now or datetime.now(timezone.utc)
    schema = json.loads((ROOT/'schemas'/'packet.schema.json').read_text())
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(packet))
    if errors:
        return {'structurally_valid':False, 'blockers':[
            {'code':'SCHEMA', 'detail':'.'.join(map(str,e.absolute_path))+': '+e.message}
            for e in errors], 'ready_for_owner_review':False,
            'owner_approved_draft':False, 'this_validator_does_not_dispatch':True}
    blockers=[]
    def fail(code, detail):
        item={'code':code,'detail':detail}
        if item not in blockers: blockers.append(item)
    def finite_numbers(value, path='packet'):
        if isinstance(value,float) and not math.isfinite(value): fail('NONFINITE_NUMBER',path)
        elif isinstance(value,dict):
            for k,v in value.items(): finite_numbers(v,path+'.'+k)
        elif isinstance(value,list):
            for i,v in enumerate(value): finite_numbers(v,path+'.'+str(i))
    finite_numbers(packet)
    if packet['state'] not in ['needs_owner_review','approved_draft']:
        fail('INCOMPLETE_WORKFLOW_STATE',packet['state'])
    maps={}
    for group in ['sources','claims','games','media','segments','variants']:
        items=packet[group]
        maps[group]={x['id']:x for x in items}
        if len(items)!=len(maps[group]): fail('DUPLICATE_ID',group)
    src=maps['sources']; claims=maps['claims']; media=maps['media']; segs=maps['segments']; games=maps['games']
    for s in src.values():
        if s['expires_at'] and moment(s['expires_at'])<=now: fail('EXPIRED_SOURCE',s['id'])
    for c in claims.values():
        for sid in c['source_ids']:
            if sid not in src: fail('UNKNOWN_SOURCE',c['id']+': '+sid)
        if c['status'] in ['unsupported','expired','proposed']:
            fail('UNFINISHED_CLAIM',c['id'])
        if c['evidence_type']=='proposed' and c['status'] in ['verified','attributed']:
            fail('EVIDENCE_STATUS_CONTRADICTION',c['id'])
        if c['evidence_type']!='proposed' and not c['source_ids']:
            fail('UNSOURCED_CLAIM',c['id'])
        if c['expires_at'] and moment(c['expires_at'])<=now: fail('EXPIRED_CLAIM',c['id'])
        for sid in c['source_ids']:
            if sid in src and src[sid]['access_status']!='inspected': fail('SOURCE_NOT_INSPECTED',sid)
    for g in games.values():
        sid=g['official_description_source_id']
        if sid not in src: fail('MISSING_OFFICIAL_DESCRIPTION',g['id'])
        elif src[sid]['access_status']!='inspected': fail('SOURCE_NOT_INSPECTED',sid)
        for kind in ['critic','steam']:
            rec=g[kind]
            if rec['status'] in ['blocked','requires_refresh']: fail('RECEPTION_UNRESOLVED',g['id']+': '+kind)
            if rec['status']=='verified' and not rec['source_ids']: fail('UNSOURCED_RECEPTION',g['id']+': '+kind)
            if rec['status']=='verified' and (rec['value'] is None or rec['value']==''):
                fail('MISSING_RECEPTION_VALUE',g['id']+': '+kind)
            if rec['status'] in ['not_found_after_search','not_applicable'] and not rec['reason']:
                fail('MISSING_EXCEPTION_REASON',g['id']+': '+kind)
            if rec['status'] in ['not_found_after_search','not_applicable'] and rec['value'] is not None:
                fail('VALUE_ON_COVERAGE_EXCEPTION',g['id']+': '+kind)
            for sid in rec['source_ids']:
                if sid not in src: fail('UNKNOWN_SOURCE',g['id']+': '+sid)
                elif src[sid]['access_status']!='inspected': fail('SOURCE_NOT_INSPECTED',sid)
    for s in segs.values():
        if s['end']<=s['start']: fail('BAD_SEGMENT_TIME',s['id'])
        for cid in s['claim_ids']:
            if cid not in claims: fail('UNKNOWN_CLAIM',s['id']+': '+cid)
        for gid in s['reception_for']:
            if gid not in games: fail('UNKNOWN_GAME',s['id']+': '+gid)
        if not s['shots']: fail('MISSING_VISUAL',s['id'])
        for shot in s['shots']:
            aid=shot['media_id']
            if aid not in media:
                fail('UNKNOWN_MEDIA',aid); continue
            asset=media[aid]
            if asset['status']!='available' or not asset['local_reference']: fail('MEDIA_REQUIRED',aid)
            if asset['status']=='available' and (asset['duration_seconds'] is None or asset['duration_seconds']<=0):
                fail('UNKNOWN_MEDIA_DURATION',aid)
            if asset['rights_status']!='cleared' or not asset['rights_evidence']: fail('RIGHTS_UNRESOLVED',aid)
            if shot['source_out']<=shot['source_in']: fail('BAD_SOURCE_RANGE',aid)
            if asset['duration_seconds'] is not None and shot['source_out']>asset['duration_seconds']:
                fail('SOURCE_RANGE_OVERFLOW',aid)
    for v in packet['variants']:
        used=[]
        for sid in v['segment_ids']:
            if sid not in segs: fail('UNKNOWN_SEGMENT',v['id']+': '+sid)
            else: used.append(segs[sid])
        for gid in v['game_ids']:
            if gid not in games: fail('UNKNOWN_GAME',v['id']+': '+gid)
        if v['kind']=='narrated_video':
            audible={gid for s in used if s['voiceover'].strip() for gid in s['reception_for']}
            for gid in audible-set(v['game_ids']): fail('FEATURED_GAME_OMITTED',v['id']+': '+gid)
            for gid in v['game_ids']:
                if gid not in audible: fail('MISSING_SPOKEN_RECEPTION',v['id']+': '+gid)
            previous_end=0
            for s in used:
                if s['start']<previous_end: fail('OVERLAPPING_VOICE_SEGMENTS',v['id'])
                previous_end=s['end']
            if used and used[-1]['end']>v['target_seconds']: fail('VARIANT_TIME_OVERFLOW',v['id'])
        elif v['game_ids']:
            parent=maps['variants'].get(v['parent_variant_id'])
            if not parent or parent['kind']!='narrated_video': fail('GAMING_COMPANION_WITHOUT_PARENT',v['id'])
            elif not set(v['game_ids']).issubset(set(parent['game_ids'])):
                fail('COMPANION_GAME_NOT_IN_PARENT',v['id'])
        if v['technical_capability_status']!='verified': fail('PLATFORM_NOT_VERIFIED',v['id'])
        if v['disclosure_status']!='reviewed': fail('DISCLOSURE_NOT_REVIEWED',v['id'])
    featured_any={gid for v in packet['variants'] for gid in v['game_ids']}
    for gid in set(games)-featured_any: fail('GAME_UNUSED_IN_VARIANTS',gid)
    for note in packet['blockers']: fail('DECLARED_BLOCKER',note)
    ap=packet['approval']
    for field in ['evidence_reviewed','actual_media_reviewed','voice_render_timed']:
        if not ap[field]: fail('REVIEW_NOT_COMPLETED',field)
    if packet['state']=='research_example': fail('EXAMPLE_ONLY','Research fixture cannot be an approved production.')
    approved=ap['owner_approved'] and ap['approved_revision']==ap['revision'] and ap['approved_at'] is not None
    if ap['owner_approved'] and not approved: fail('APPROVAL_REVISION_MISMATCH',ap['revision'])
    if packet['state']=='approved_draft' and not approved: fail('APPROVED_STATE_WITHOUT_APPROVAL',ap['revision'])
    ready=not blockers
    return {'structurally_valid':True,'blockers':blockers,'ready_for_owner_review':ready,
            'owner_approved_draft':bool(ready and approved),'this_validator_does_not_dispatch':True,
            'limitation':'Checks references and declared states only. A trusted verifier must inspect facts, actual media, narration, rights and account capabilities.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet')
    parser.add_argument('--now',help='ISO 8601 clock override for reproducible fixture tests only')
    args=parser.parse_args()
    try:
        def reject_constant(value): raise ValueError('Nonstandard JSON number: '+value)
        packet=json.loads(Path(args.packet).read_text(),parse_constant=reject_constant)
        result=validate_packet(packet, moment(args.now) if args.now else None)
    except (OSError, ValueError) as error:
        print(json.dumps({'structurally_valid':False,'error':str(error),'this_validator_does_not_dispatch':True}))
        return 3
    print(json.dumps(result, indent=2))
    return 3 if not result['structurally_valid'] else (0 if result['ready_for_owner_review'] else 2)

if __name__=='__main__': raise SystemExit(main())
