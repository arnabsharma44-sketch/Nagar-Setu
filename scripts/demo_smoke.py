"""End-to-end smoke script for the ROADGUARD AI vertical slice.

Runs the whole journey against a live API instance:

    sign in -> upload CCTV clip -> background processing -> candidate event ->
    human review -> investigation -> asset/department/contract match ->
    draft analysis -> recommendation approval -> work order -> completion
    evidence -> independent verification -> audit trail

It requires a seeded database (``python scripts/seed_database.py``) and a running
API. Processing is performed by the polling worker, which this script runs inline
in-process by default so the demonstration is one command.

Usage::

    python scripts/demo_smoke.py --api http://127.0.0.1:8000
    python scripts/demo_smoke.py --api http://127.0.0.1:8000 --external-worker
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
sys.path.insert(0, str(REPO_ROOT / "ai-engine"))

DEMO_PASSWORD = os.environ.get("DEMO_SEED_PASSWORD", "RoadguardDemo#2026")
SAMPLE_CLIP = REPO_ROOT / "datasets" / "sample_videos" / "demo_intersection_synthetic.mp4"


class StepFailed(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise StepFailed(message)


def absolute_url(base_url: str, url: str) -> str:
    """Signed URLs are either API-relative (local backend) or absolute (S3)."""
    return url if url.startswith(("http://", "https://")) else f"{base_url}{url}"


class Client:
    def __init__(self, base_url: str) -> None:
        self.http = httpx.Client(base_url=base_url, timeout=60.0)
        self.user: dict = {}

    def _headers(self) -> dict[str, str]:
        token = self.http.cookies.get("roadguard_csrf")
        return {"x-csrf-token": token} if token else {}

    def login(self, email: str) -> None:
        response = self.http.post(
            "/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD}
        )
        check(response.status_code == 200, f"login {email} failed: {response.status_code} {response.text[:300]}")
        self.user = response.json()["data"]["user"]

    def get(self, path: str, **kwargs) -> dict:
        response = self.http.get(path, **kwargs)
        check(response.status_code < 300, f"GET {path} -> {response.status_code}: {response.text[:300]}")
        return response.json()

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self.http.post(path, headers=self._headers(), **kwargs)

    def patch(self, path: str, **kwargs) -> httpx.Response:
        return self.http.patch(path, headers=self._headers(), **kwargs)


def run(base_url: str, *, external_worker: bool) -> None:
    operator = Client(base_url)
    reviewer = Client(base_url)
    engineer = Client(base_url)
    auditor = Client(base_url)

    print("1/12 sign in as operations user")
    operator.login("ops@demo.roadguard.ai")
    permissions = operator.user["permissions"]
    check("video:upload" in permissions, "expected video:upload permission")
    print(f"    role={operator.user['role']} org={operator.user['organization']['slug']}")

    print("2/12 upload synthetic CCTV clip")
    content_type = "video/mp4"
    size = SAMPLE_CLIP.stat().st_size
    response = operator.post(
        "/api/v1/videos/upload-url",
        json={
            "filename": SAMPLE_CLIP.name,
            "content_type": content_type,
            "file_size_bytes": size,
            "camera_id": operator.get("/api/v1/cameras")["data"][0]["id"],
            "recorded_at": "2026-11-17T09:30:00Z",
            "source_type": "upload",
        },
    )
    check(response.status_code == 201, f"upload-url failed: {response.status_code} {response.text[:400]}")
    upload = response.json()["data"]
    video_id = upload["video_id"]

    upload_response = httpx.put(
        absolute_url(base_url, upload["upload_url"]),
        content=SAMPLE_CLIP.read_bytes(),
        headers={"content-type": content_type},
        timeout=120.0,
    )
    check(upload_response.status_code < 300, f"upload PUT failed: {upload_response.status_code}")
    response = operator.post(f"/api/v1/videos/{video_id}/complete-upload")
    check(response.status_code == 200, f"complete-upload failed: {response.status_code} {response.text[:400]}")
    print(f"    video={video_id} status={response.json()['data']['status']}")

    print("3/12 background processing")
    jobs = operator.get(f"/api/v1/jobs?video_id={video_id}")["data"]
    check(len(jobs) == 1, "expected exactly one processing job")
    job_id = jobs[0]["id"]
    if external_worker:
        print(f"    job={job_id} queued; the polling worker processes it asynchronously")
        import time

        deadline = time.time() + 180
        job = jobs[0]
        while time.time() < deadline:
            job = operator.get(f"/api/v1/jobs/{job_id}")["data"]
            if job["status"] in {"succeeded", "failed"}:
                break
            time.sleep(2)
    else:
        from ai_engine.workers.runner import process_job

        result = process_job(job_id)
        job = operator.get(f"/api/v1/jobs/{job_id}")["data"]
        print(f"    worker result: {result.get('status')}")
    check(job["status"] == "succeeded", f"job did not succeed: {job['status']} {job.get('error_message_safe')}")
    print(
        f"    model={job['model_name']} v{job['model_version']} rules={job['event_rules_version']} "
        f"events={job['result_summary'].get('incidents_created')}"
    )

    print("4/12 candidate events")
    incidents = operator.get(f"/api/v1/incidents?video_id={video_id}")["data"]
    check(bool(incidents), "expected at least one candidate event from the demo clip")
    incident = incidents[0]
    check(incident["source_kind"] == "ai_candidate", "expected source_kind ai_candidate")
    check(incident["review_status"] == "pending", "new candidate must be pending review")
    check(incident["limitations"], "candidate must expose its limitations")
    print(
        f"    type={incident['incident_type']} score={incident['model_score']} "
        f"window={incident['start_offset_seconds']}-{incident['end_offset_seconds']}s"
    )

    print("5/12 evidence artefacts")
    evidence = operator.get(f"/api/v1/incidents/{incident['id']}/evidence")["data"]
    check(bool(evidence), "expected generated evidence")
    frame = next((item for item in evidence if item["evidence_type"] == "annotated_frame"), None)
    check(frame is not None, "expected an annotated frame")
    url = operator.get(f"/api/v1/evidence/{frame['id']}/url")["data"]["url"]
    fetch = httpx.get(absolute_url(base_url, url), timeout=60.0)
    check(fetch.status_code == 200 and len(fetch.content) > 1000, "annotated frame not retrievable")
    print(f"    evidence={len(evidence)} items, annotated frame {len(fetch.content)} bytes")

    print("6/12 reviewer confirms the candidate event")
    reviewer.login("reviewer@demo.roadguard.ai")
    response = reviewer.patch(
        f"/api/v1/incidents/{incident['id']}/review",
        json={
            "decision": "confirmed",
            "notes": "Reviewed the annotated frame and clip; the conflict matches the configured rule.",
        },
    )
    check(response.status_code == 200, f"review failed: {response.status_code} {response.text[:300]}")
    check(response.json()["data"]["review_status"] == "confirmed", "review status not persisted")
    print("    review_status=confirmed")

    print("7/12 open an investigation on the nearby asset")
    nearby = operator.get(
        "/api/v1/assets/nearby?latitude=20.2961&longitude=85.8245&radius_meters=400"
    )["data"]
    check(bool(nearby), "expected seeded nearby assets")
    asset = nearby[0]
    response = reviewer.post(
        "/api/v1/investigations",
        json={
            "incident_id": incident["id"],
            "asset_id": asset["asset_id"],
            "title": "Investigate candidate near miss at the Janpath corridor",
            "summary": "Opened from the reviewed candidate event for field verification.",
            "assigned_department_id": operator.get("/api/v1/departments")["data"][0]["id"],
        },
    )
    check(response.status_code == 201, f"investigation create failed: {response.status_code} {response.text[:400]}")
    investigation_id = response.json()["data"]["id"]
    print(f"    case={response.json()['data']['case_number']}")

    print("8/12 asset/department/contract record match")
    detail = operator.get(f"/api/v1/investigations/{investigation_id}")["data"]
    responsibility = detail["responsibility"]
    check(responsibility is not None, "expected a responsibility payload")
    check(
        responsibility["status"] in {"matched_records", "ambiguous_match", "missing_contract_data",
                                      "requires_field_verification", "no_asset_match"},
        "unexpected responsibility status",
    )
    check(
        "liabilit" in responsibility["disclaimer"].lower()
        or "no liability" in responsibility["disclaimer"].lower(),
        "responsibility payload must carry a no-liability disclaimer",
    )
    print(
        f"    status={responsibility['status']} department={responsibility['owning_department_name']} "
        f"contracts={[c['contract_number'] for c in responsibility['contracts']]}"
    )

    print("9/12 draft investigation analysis")
    response = reviewer.post(f"/api/v1/investigations/{investigation_id}/analyze")
    check(response.status_code == 200, f"analysis failed: {response.status_code} {response.text[:400]}")
    analysis = response.json()["data"]
    check(analysis["observed_facts"], "analysis must contain observed facts")
    check(analysis["human_verification_required"] is True, "analysis must require human verification")
    print(
        f"    source={analysis['analysis_source']} hypotheses={len(analysis['potential_root_causes'])} "
        f"missing={len(analysis['missing_information'])}"
    )

    print("10/12 draft recommendation and independent approval")
    response = reviewer.post(
        f"/api/v1/investigations/{investigation_id}/recommendations",
        json={
            "recommendation_text": "Restore pedestrian crossing markings and review signal timing at the junction.",
            "rationale": (
                "The reviewed candidate conflict occurred at a crossing with a recorded fair asset "
                "condition; a site review is the documented next step."
            ),
            "priority": "high",
        },
    )
    check(response.status_code == 201, f"recommendation create failed: {response.status_code} {response.text[:300]}")
    recommendation_id = response.json()["data"]["id"]

    self_approval = reviewer.patch(
        f"/api/v1/recommendations/{recommendation_id}/review",
        json={"decision": "approved", "notes": "Attempting self approval."},
    )
    check(self_approval.status_code == 409, "author must not be able to approve their own draft")

    operator.login("ops@demo.roadguard.ai")
    approval = operator.patch(
        f"/api/v1/recommendations/{recommendation_id}/review",
        json={"decision": "approved", "notes": "Approved after reviewing the evidence and rationale."},
    )
    check(approval.status_code == 200, f"approval failed: {approval.status_code} {approval.text[:300]}")
    print("    self-approval blocked, independent approval recorded")

    print("11/12 work order, completion evidence and channel separation")
    departments = operator.get("/api/v1/departments")["data"]
    roads = next(d for d in departments if "Roads" in d["name"])
    response = operator.post(
        "/api/v1/work-orders",
        json={
            "investigation_id": investigation_id,
            "recommendation_id": recommendation_id,
            "assigned_department_id": roads["id"],
            "title": "Restore crossing markings at DEMO Janpath Junction",
            "description": "Repaint crossing markings and confirm signal timing with the department.",
            "priority": "high",
            "due_date": "2026-12-20",
        },
    )
    check(response.status_code == 201, f"work order create failed: {response.status_code} {response.text[:300]}")
    work_order = response.json()["data"]
    work_order_id = work_order["id"]
    print(f"    work order={work_order['work_order_number']} status={work_order['status']}")

    engineer.login("engineer@demo.roadguard.ai")
    acknowledge = engineer.patch(
        f"/api/v1/work-orders/{work_order_id}",
        json={"status": "assigned", "note": "Accepted by the department engineer."},
    )
    check(acknowledge.status_code == 200, f"accept failed: {acknowledge.status_code} {acknowledge.text[:300]}")
    transition = engineer.patch(
        f"/api/v1/work-orders/{work_order_id}",
        json={"status": "in_progress", "note": "Field team scheduled."},
    )
    check(transition.status_code == 200, f"transition failed: {transition.status_code} {transition.text[:300]}")

    evidence_bytes = (
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 2048
    )  # minimal placeholder image payload for the demo
    upload_evidence = engineer.post(
        f"/api/v1/work-orders/{work_order_id}/evidence",
        files={"file": ("completion_photo.png", evidence_bytes, "image/png")},
        data={"label": "Repainted crossing markings"},
    )
    check(upload_evidence.status_code == 201, f"evidence upload failed: {upload_evidence.status_code} {upload_evidence.text[:300]}")
    evidence_id = upload_evidence.json()["data"]["id"]

    completion = engineer.post(
        f"/api/v1/work-orders/{work_order_id}/completion",
        json={
            "completion_notes": "Markings repainted and signal timing checked with the department engineer.",
            "evidence_ids": [evidence_id],
        },
    )
    check(completion.status_code == 200, f"completion failed: {completion.status_code} {completion.text[:300]}")
    check(
        completion.json()["data"]["status"] == "completed_pending_verification",
        "work order should await verification",
    )

    print("12/12 independent verification and audit trail")
    submitter_verify = engineer.post(
        f"/api/v1/work-orders/{work_order_id}/verifications",
        json={"verification_status": "accepted", "notes": "Verifying my own submission."},
    )
    check(
        submitter_verify.status_code in {403, 409},
        f"the completing department user must not verify: got {submitter_verify.status_code}",
    )

    reviewer.login("reviewer@demo.roadguard.ai")
    verification = reviewer.post(
        f"/api/v1/work-orders/{work_order_id}/verifications",
        json={
            "verification_status": "accepted",
            "notes": "Evidence reviewed; markings restored and signal timing confirmed.",
        },
    )
    check(verification.status_code == 200, f"verification failed: {verification.status_code} {verification.text[:400]}")
    check(verification.json()["data"]["status"] == "verified", "work order not verified")

    auditor.login("auditor@demo.roadguard.ai")
    audit = auditor.get("/api/v1/audit-logs?limit=100")["data"]
    actions = {entry["action"] for entry in audit}
    for expected in (
        "auth.login",
        "video.upload_completed",
        "video.processing_queued",
        "incident.reviewed",
        "investigation.created",
        "recommendation.approved",
        "work_order.created",
        "work_order.completion_submitted",
        "work_order.verification_accepted",
    ):
        check(expected in actions, f"missing audit action: {expected}")
    print(f"    audit entries={len(audit)} verified")

    blocked = auditor.post(
        "/api/v1/work-orders",
        json={"investigation_id": str(investigation_id), "assigned_department_id": roads["id"],
              "title": "forbidden", "description": "forbidden"},
    )
    check(blocked.status_code == 403, "auditor should not create work orders")

    print("\nOK: full workflow completed end to end.")


def main() -> int:
    parser = argparse.ArgumentParser(description="ROADGUARD AI end-to-end smoke test")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--external-worker", action="store_true", help="wait for a separate worker")
    args = parser.parse_args()
    try:
        run(args.api, external_worker=args.external_worker)
    except StepFailed as exc:
        print(f"\nFAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
