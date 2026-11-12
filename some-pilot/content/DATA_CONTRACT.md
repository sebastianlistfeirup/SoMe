# Data contract and integration boundary — version 1.1

The target is a complete SoMe production and publishing flow:

**Bible → researched script → actual thumbnail, title, caption and hashtags → ElevenLabs narration → rendered destination videos → complete backend draft → Sebastian approves or rejects → automatic publication to the approved Facebook, Instagram, YouTube and TikTok accounts.**

Approval is the final editorial decision after Sebastian can review the actual deliverables. It must not mean approving a text outline and discovering the final video later. On approval, the existing publishing service should act automatically when its live prerequisites pass. Rejection returns the draft for changes and prevents dispatch. This kit specifies and checks the records; it does not implement the backend, ElevenLabs client, renderer, credentials or social API adapters.

`config.json` declares `automatic_after_owner_approval`, enables that target architecture, and defaults to all four destinations. Actual voice IDs, Sebastian's backend identity, account IDs and connection references remain unconfigured. Those nulls are integration work, not fake credentials or evidence that a connection works. Configure selected destinations through the real backend; never infer accounts from display names.

## Two distinct contracts

The schemas use JSON Schema Draft 2020-12. The packet, analytics and workflow records use `schema_version: "1.1.0"`. Their `.invalid` schema identifiers do not represent hosted services.

- `schemas/packet.schema.json` describes editorial evidence, games, footage, narrated segments and platform variants. `tools/validate_packet.py` remains the editorial structural gate.
- `schemas/workflow.schema.json` describes the finished production payload, backend draft, owner decision, preflight and per-destination delivery ledger. `tools/validate_workflow.py` computes local dispatch eligibility and authorization.

Both tools return `this_validator_does_not_dispatch: true`. That describes what the validation programs do. It does **not** permanently disable publishing in the target machine. The separate workflow result can set `dispatch_authorized: true` and return approved `dispatch_destination_ids` when all required trusted production records are present. The existing publisher consumes that decision and performs the actual calls. Merely passing the editorial packet gate is insufficient.

## Editorial records

A source records an inspected location, retrieval and expiry times, scope and access status. A claim links an assertion to that evidence. A game identifies the exact release and platform with separate official description, critic and Steam records. A media item distinguishes requested footage from available material and records provenance and rights. A segment links spoken narration, claims, reception declarations and source footage ranges. A variant assembles segments for one destination format.

`reception_for` is an index, not proof of speech. A trusted verifier must compare the rendered narration or transcript with each game's scoped reception or truthful exception. Similarly, `actual_media_reviewed` requires viewing the relevant footage; a filename cannot establish it. When timing changes, create new segment IDs rather than reusing obsolete timecodes.

In the idea bank, `target_seconds` estimates the parent story. `recommended_platforms` includes possible independently edited derivatives. It does not mean uploading a ten-minute parent unchanged as a Short.

Analytics preserves native metric definitions, populations, denominators and measurement windows. Missing values remain null with an availability reason. Raw imports remain immutable.

## What a complete production payload contains

`payload` is the immutable material Sebastian approves. It includes the Bible version, content revision, lane, chosen Gaming or AI voice profile, editorial-packet digest, artifact manifest and every selected destination. Crossover stories explicitly select one of the existing voice profiles.

The manifest includes actual script files, actual thumbnail image files, actual ElevenLabs audio, subtitle/caption files and actual rendered videos. Each artifact has an ID, kind, relative storage path, SHA-256, byte count, MIME type and completion status. Narration additionally records `provider: "elevenlabs"` and the configured voice ID. A thumbnail prompt or cover direction is not a thumbnail artifact. An ElevenLabs request ID or proposed voiceover text is not a completed audio file. A render job ID is not a completed video.

Each destination binds its platform, actual account ID, variant ID, script, narration, thumbnail, subtitle/caption and video artifact IDs, title, caption, hashtags and publication options. A derivative can reuse a file only when that exact file has been checked for the destination. Different wording or timing needs the corresponding script and narration artifacts. The finished video must contain the approved narration. The trusted media review checks decoding, image dimensions, duration, audible speech, voice timing, cuts, caption positioning, content and platform compatibility.

The local workflow validator resolves every listed file beneath the supplied artifact root, rejects paths escaping that root, reads the real bytes, and checks nonempty size and SHA-256. It streams large files. It checks required artifact kinds and MIME declarations. It does not decode audio/video or prove that a declared MIME type describes the bytes; that is the trusted renderer/verifier's responsibility. Storage adapters must materialize or securely resolve remote objects before this local check, or implement equivalent immutable-object integrity checks in the existing machine.

Publication options record the exact native settings used by the adapter: for example visibility, cover handling, disclosure and timing where supported. The backend always keeps the actual thumbnail for review. How that image is applied remotely must follow the verified destination capability; do not assume every API supports the same custom-cover operation. Resolve native settings before approval and include them in the payload. `publication_options.timing` is `immediate` or `scheduled`; `publish_at` is null for immediate publication or an explicit UTC timestamp for a scheduled destination. The gate releases a scheduled destination only when that timestamp is due. Subtitle/caption files are actual required artifacts, distinct from the social post caption text.

## Backend revision, approval and hashing

The backend stores the complete payload and its revision before entering `needs_owner_review`. Its preview lets Sebastian inspect the actual video, thumbnail, narration and destination text, together with selected accounts and material source notes. It records the persisted payload hash and save time.

The `payload_hash()` helper hashes UTF-8 JSON produced with sorted keys, no optional whitespace, `ensure_ascii=False` and `allow_nan=False`. Use this helper's canonical bytes consistently in the backend and dispatcher; another language should consume those exact stored bytes or match that serialization. This is a content integrity binding, not a digital signature or proof of an authenticated approval. JSON NaN and infinities are rejected.

An approval record contains the decision, authenticated reviewer ID, decision time, backend event ID, exact revision, payload hash and exact destination/account pairs. The configured owner ID must be Sebastian's real backend identity. The generative writer cannot supply or change that event. `pending` and `rejected` decisions never authorize dispatch. The backend itself must also be in an approved dispatch state; an old approval event cannot release a draft currently awaiting owner review.

Any change to script, narration, thumbnail, rendered video, title, caption, hashtags, selected account, destination, visibility or other publication option changes the payload and invalidates approval. Changed file bytes also fail integrity checks even when a revision label was not incremented. Save a new revision and obtain a new decision. Final source refresh records can change outside the content payload only when the approved content remains correct; changed facts require content revision and renewed approval.

A complete draft can be reviewed and approved while one publishing connection is temporarily unavailable. Show the blocked destination clearly. Missing or unfinished media prevents a complete review; a connection outage prevents that destination's dispatch. Restoring the same account and capabilities without changing the approved payload permits publication without a second approval, subject to a current source check.

## Protected fields and integration ownership

Treat the model's draft JSON as untrusted input. The backend must enforce write ownership, not merely ask the model to respect it.

| Record or field | Trusted writer |
| --- | --- |
| Artifact hashes, byte counts, completed files and media review | Renderer, storage resolver and verification service |
| `backend`, persisted payload hash and revision | Backend draft service |
| `approval`, reviewer ID and backend event ID | Authenticated Sebastian approval/rejection route |
| Editorial gate outcome and source-refresh evidence | Verification service reading the actual evidence |
| Account IDs, connection references and current capabilities | Configured account integration service |
| Delivery attempts, post IDs and reconciliation receipts | Publishing adapter and append-only delivery ledger |

The supplied validators inspect these records; they do not authenticate their producers. Calling a flag `verified` in model output cannot replace the corresponding trusted check. Credentials stay in the existing secret store, outside prompts, artifacts, JSON examples and logs. A connection reference is an opaque binding to that service, not a raw token.

## Dispatch preflight and per-destination lifecycle

Immediately before dispatch, check the current source-refresh result against the exact approved payload. Its evidence reference, check time and validity window must be present and current. A changed or failed check blocks dispatch. Recheck actual destination capability and permissions against the selected account, not just a generic platform name. Each capability record has a verified account binding, connection reference, checked time and expiry.

The delivery ledger is per destination. It binds the payload hash and an idempotency key derived from story, revision, destination, account and payload. The machine should persist a pending delivery before the first request, then atomically claim it as in progress. The local validator does not implement database locks, transactions or request dispatch; those belong in the existing publisher.

- `pending` with zero attempts can make its first request after all gates pass.
- `in_progress` is not retried by another worker.
- `failed` can retry only that destination, when the failure is classified retryable and no unresolved outcome remains.
- `unknown` means the request may have reached the platform. Reconcile using the adapter's permitted status lookup or receipt before any retry. A confirmed absence must have a timestamped reconciliation receipt before transition to retryable failure. Never erase an unknown outcome by resetting a row to pending or clearing its reconciliation requirement.
- `published`, a recorded platform post ID, or a confirmed published reconciliation result prevents reupload. Record the receipt and URL where available. A later failure on another platform does not republish successful destinations.

Keep attempt and reconciliation history append-only in the real backend. The fixture validator checks the supplied current ledger; only that protected history can establish legitimate state transitions. An intentional replacement post requires an explicit new publication decision, not resetting a successful ledger entry. Editing an already published post also needs its own supported, authorized operation.

`eligible_destination_ids` means the contract conditions are met for those destinations, before the explicit fixture/placeholder exclusion. `dispatch_destination_ids` is the actual list an integrated dispatcher may consume. A synthetic record always produces an empty dispatch list, even when its fictional prerequisites exercise a complete approved path. A partial failure produces work only for eligible remaining destinations. If every destination is already published, there is no new dispatch work.

## Examples, tests and scope

`examples/gaming_packet_needs_capture.json` is deliberately incomplete: real research leads, dated reception, requested footage and no owner approval. Its times are fixture values, not a real production audit log. The complete creative scripts are in the Bible. `examples/analytics_synthetic.json` contains fictional demonstration data and must never enter live reporting.

`tests/test_workflow.py` builds a clearly marked synthetic approved workflow in a temporary directory. Its files are nonempty test bytes, not actual thumbnails, voice recordings or rendered videos; its owner and capability events are fictional. This exercises file integrity, metadata, voice binding, backend approval, expiry and retry behavior. The fixture flag and placeholder checks prevent its dispatch. No credentials or actual approval events are included.

From the kit directory:

```bash
python -m unittest discover -s tests -v
python tools/validate_packet.py examples/gaming_packet_needs_capture.json
python tools/validate_workflow.py /path/to/workflow.json --artifact-root /path/to/artifacts
```

The editorial regression tests are preserved and additional lifecycle tests cover the production contract. The unfinished editorial example returns exit code 2 with blockers. Workflow exit code 0 means at least one destination is authorized by the supplied trusted records; 2 means blocked, synthetic or no work remains; 3 means malformed input. Neither CLI performs a publication.

Passing these tests demonstrates local contract behavior only. The real acceptance run must generate ElevenLabs narration and actual destination files, save a backend draft, accept Sebastian's authenticated decision, and exercise the configured publishing adapters. This kit makes no claim that those integrations are currently attached or operational.
