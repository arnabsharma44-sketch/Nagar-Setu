# Video Pipeline Report

## Uploaded video

| Case | Result | Evidence |
| --- | --- | --- |
| Valid MP4 (800×450, 25 fps, 12 s) | PASS | Uploaded as video `1c518368…`, job succeeded, 3,009 detections across runs |
| MIME/extension mismatch | PASS | 415 `UNSUPPORTED_MEDIA_TYPE`; no job created |
| Oversized file | PASS | 413 `PAYLOAD_TOO_LARGE`; no job created |
| Corrupt/truncated media | PASS (unit) | Rejected at validation; `validation_error` recorded on the row |
| AVI container | NOT TESTED | No AVI fixture; FFmpeg supports it, but no claim is made |
| MOV container | NOT TESTED | Same |
| Empty file | PASS (unit) | Rejected |
| Repeated upload | PASS | `idempotency_key` unique per `(organization, key)`; duplicate job prevented |
| Interrupted upload | NOT TESTED | No resumable-upload client to drive it |
| Object-storage failure | NOT TESTED | Local backend used; MinIO healthy but no fault injection |

## Processing

```
video 1c518368  status=processing
job   312c3194  queued → succeeded, progress 100%
model synthetic-scene-colour-marker  v=synthetic_scene_v1  rules=1.0.0
event near_miss_candidate  score=0.436  window 3.0–9.0 s
evidence 2 items, annotated frame 63,211 bytes
```

- Work is never processed inside the request: the upload returns a queued job and the worker
  leases it (`lease_owner`, `lease_expires_at`, `attempts`).
- The external Celery/polling worker processed the job in the end-to-end run; the in-process
  runner is a demo convenience only.
- Retry semantics: a non-retryable job returns 409 `JOB_NOT_RETRYABLE`; the attempt counter
  bounds retries.

## Live CCTV

| Case | Result |
| --- | --- |
| Valid RTSP feed | **BLOCKED** — no authorised feed |
| Invalid URL / disconnected / auth failure / reconnection | Covered by the simulated path's error handling; not exercised against a real camera |
| Simulated-live replay | PASS (implemented) — explicitly labelled `demo_replay` in the API and UI |
| Camera status update | PASS (data) — `connection_status` values offline/unknown are displayed honestly |
| Credentials exposure | PASS — frontend contains no `rtsp://` strings; rows store `secret_reference` |

The simulated feed is never presented as a real police feed: the session row is
`mode="demo_replay"` with the description "Simulated live replay of a stored demonstration clip",
and the DEMO banner is on every command page.

## Resource behaviour

Worker CPU/memory during processing was not instrumented; queue depth reached 4 queued jobs at
one point with no failures. A large-file throughput test was not run.
