"use client";

import { useState } from "react";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/useApi";
import { api, ApiError } from "@/lib/api";
import {
  Button,
  Card,
  CardHeader,
  DataTable,
  ErrorState,
  Field,
  Input,
  LoadingRows,
  PageHeader,
  PermissionNotice,
  Row,
  StatusBadge,
} from "@/components/ui";
import { formatBytes, formatDateTime, formatSeconds } from "@/lib/format";
import type { Camera, Job, UploadSession, Video } from "@/lib/types";

type UploadStage = "idle" | "signing" | "uploading" | "completing" | "processing" | "done";

export default function VideosPage() {
  const { has, meta } = useSession();
  const videos = useApi<Video[]>("/api/v1/videos?limit=25");
  const jobs = useApi<Job[]>("/api/v1/jobs?limit=25");
  const cameras = useApi<Camera[]>("/api/v1/cameras?limit=100");
  const [stage, setStage] = useState<UploadStage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [activeVideo, setActiveVideo] = useState<string | null>(null);

  if (!has("video:read")) return <PermissionNotice tone="command" permission="video:read" />;

  const maxBytes = meta?.max_upload_bytes ?? 200 * 1024 * 1024;

  async function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    const form = new FormData(event.currentTarget);
    const file = form.get("file");
    const cameraId = form.get("camera_id");
    if (!(file instanceof File) || file.size === 0) {
      setError("Choose a video file first.");
      return;
    }
    if (file.size > maxBytes) {
      setError(`That file is ${formatBytes(file.size)}; the limit is ${formatBytes(maxBytes)}.`);
      return;
    }
    try {
      setStage("signing");
      const uploadSession = await api.post<UploadSession>("/api/v1/videos/upload-url", {
        filename: file.name,
        content_type: file.type || "video/mp4",
        file_size_bytes: file.size,
        camera_id: cameraId ? String(cameraId) : null,
        recorded_at: null,
        source_type: "upload",
      });
      setStage("uploading");
      await api.uploadObject(uploadSession.upload_url, file, file.type || "video/mp4");
      setStage("completing");
      await api.post(`/api/v1/videos/${uploadSession.video_id}/complete-upload`);
      setStage("processing");
      await api.post(`/api/v1/videos/${uploadSession.video_id}/process`, { force_reprocess: false });
      setActiveVideo(uploadSession.video_id);
      setStage("done");
      setNotice(
        "Upload completed and queued for background processing. The worker validates the media, runs detection and creates candidate events.",
      );
      videos.reload();
      jobs.reload();
    } catch (err) {
      setStage("idle");
      setError(err instanceof ApiError ? err.message : "The upload failed.");
    }
  }

  async function retry(videoId: string) {
    setError(null);
    try {
      await api.post(`/api/v1/videos/${videoId}/process`, { force_reprocess: true });
      setNotice("Reprocessing requested.");
      jobs.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not request reprocessing.");
    }
  }

  const busy = stage !== "idle" && stage !== "done";
  const stageLabel: Record<UploadStage, string> = {
    idle: "Upload and process",
    signing: "Requesting upload URL…",
    uploading: "Uploading…",
    completing: "Confirming upload…",
    processing: "Queueing background job…",
    done: "Queued",
  };

  return (
    <>
      <PageHeader
        title="Videos and processing jobs"
        description="Uploads are written straight to private object storage with a short-lived signed URL. Processing always runs in the background worker, never inside the API request."
        tone="command"
      />

      {notice ? (
        <p className="mb-3 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mb-3 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      ) : null}

      {has("video:upload") ? (
        <Card tone="command" className="mb-4">
          <CardHeader
            title="Upload CCTV footage"
            description={`Accepted: ${(meta?.supported_content_types ?? ["video/mp4"]).join(", ")} · max ${formatBytes(maxBytes)} · max ${meta?.max_video_duration_seconds ?? 600}s`}
            tone="command"
          />
          <form onSubmit={upload} className="grid gap-3 px-4 py-4 sm:grid-cols-2">
            <Field label="Video file" tone="command" htmlFor="file" hint="Demo clip: datasets/sample_videos/demo_intersection_synthetic.mp4">
              <Input tone="command" id="file" name="file" type="file" accept="video/mp4,video/quicktime,video/x-matroska" required />
            </Field>
            <Field label="Camera (optional)" tone="command" htmlFor="camera_id">
              <select
                id="camera_id"
                name="camera_id"
                className="w-full rounded-lg border border-[#243449] bg-[#0b1320] px-3 py-2 text-sm text-slate-100"
              >
                <option value="">Unassigned</option>
                {(cameras.data ?? []).map((camera) => (
                  <option key={camera.id} value={camera.id}>
                    {camera.camera_code} — {camera.name}
                  </option>
                ))}
              </select>
            </Field>
            <div className="sm:col-span-2 flex items-center gap-3">
              <Button tone="command" type="submit" disabled={busy}>
                {stageLabel[stage]}
              </Button>
              <span className="text-xs text-slate-500">
                Uploading does not create an accident record. It creates private footage and a job.
              </span>
            </div>
          </form>
        </Card>
      ) : null}

      <div className="grid gap-4">
        <Card tone="command">
          <CardHeader title="Footage" description="Private media. Playback links are short-lived and scoped to your organization." tone="command" />
          {videos.loading ? (
            <LoadingRows tone="command" />
          ) : videos.error ? (
            <ErrorState tone="command" message={videos.error} onRetry={videos.reload} />
          ) : (
            <DataTable
              tone="command"
              head={["File", "Status", "Duration", "Size", "Uploaded", "Validation", ""]}
              empty="No footage uploaded yet."
            >
              {(videos.data ?? []).map((video) => (
                <Row key={video.id} tone="command">
                  <td className="px-4 py-2">
                    <span className="block text-slate-100">{video.original_filename}</span>
                    <span className="font-mono text-[11px] text-slate-500">{video.id.slice(0, 8)}</span>
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge status={video.status} />
                  </td>
                  <td className="px-4 py-2 tabular-nums text-slate-300">{formatSeconds(video.duration_seconds)}</td>
                  <td className="px-4 py-2 text-slate-400">{formatBytes(video.file_size_bytes)}</td>
                  <td className="px-4 py-2 text-xs text-slate-400">{formatDateTime(video.created_at)}</td>
                  <td className="px-4 py-2 text-xs text-rose-300">{video.validation_error ?? "—"}</td>
                  <td className="px-4 py-2 text-right">
                    {video.status === "failed" && has("video:process") ? (
                      <button
                        type="button"
                        onClick={() => void retry(video.id)}
                        className="text-xs text-sky-300 hover:underline"
                      >
                        Reprocess
                      </button>
                    ) : null}
                  </td>
                </Row>
              ))}
            </DataTable>
          )}
        </Card>

        <Card tone="command">
          <CardHeader
            title="Processing jobs"
            description={`Detector: ${meta?.detector_backend ?? "synthetic_scene"} · jobs are claimed by the polling worker`}
            tone="command"
            actions={
              <Button tone="command" variant="secondary" onClick={() => jobs.reload()}>
                Refresh
              </Button>
            }
          />
          {jobs.loading ? (
            <LoadingRows tone="command" />
          ) : jobs.error ? (
            <ErrorState tone="command" message={jobs.error} onRetry={jobs.reload} />
          ) : (
            <DataTable
              tone="command"
              head={["Job", "Video", "Status", "Stage", "Progress", "Model", "Events", "Completed"]}
              empty="No jobs yet."
            >
              {(jobs.data ?? []).map((job) => {
                const events =
                  typeof job.result_summary?.event_count === "number"
                    ? (job.result_summary.event_count as number)
                    : null;
                return (
                  <Row key={job.id} tone="command">
                    <td className="px-4 py-2 font-mono text-xs text-slate-400">{job.id.slice(0, 8)}</td>
                    <td className="px-4 py-2 font-mono text-xs text-slate-500">{job.video_id.slice(0, 8)}</td>
                    <td className="px-4 py-2">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">{job.stage.replace(/_/g, " ")}</td>
                    <td className="px-4 py-2 text-xs tabular-nums text-slate-300">{job.progress}%</td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {job.model_name ? `${job.model_name} ${job.model_version ?? ""}` : "—"}
                    </td>
                    <td className="px-4 py-2 text-xs tabular-nums text-slate-300">{events ?? "—"}</td>
                    <td className="px-4 py-2 text-xs text-slate-400">{formatDateTime(job.completed_at)}</td>
                  </Row>
                );
              })}
            </DataTable>
          )}
          {activeVideo ? (
            <p className="border-t border-[#1e2b3c] px-4 py-2 text-xs text-slate-500">
              Most recent upload: <span className="font-mono">{activeVideo}</span>
            </p>
          ) : null}
        </Card>
      </div>
    </>
  );
}
