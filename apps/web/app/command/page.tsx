"use client";

import Link from "next/link";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/useApi";
import { MapPanel } from "@/components/MapPanel";
import {
  Card,
  CardHeader,
  DataTable,
  ErrorState,
  LoadingRows,
  MetricCard,
  PageHeader,
  Row,
  StatusBadge,
} from "@/components/ui";
import { formatDateTime, humanise } from "@/lib/format";
import { useRealtime } from "@/lib/realtime";
import type { Camera, Incident, IncidentAnalytics, Job } from "@/lib/types";

export default function CommandOverviewPage() {
  const { session } = useSession();
  const analytics = useApi<IncidentAnalytics>("/api/v1/incidents/analytics");
  const incidents = useApi<Incident[]>("/api/v1/incidents?limit=6");
  const cameras = useApi<Camera[]>("/api/v1/cameras?limit=50");
  const jobs = useApi<Job[]>("/api/v1/jobs?limit=5");
  const realtime = useRealtime((event) => {
    if (event.event_type.startsWith("incident.")) incidents.reload();
    if (event.event_type.startsWith("video.")) jobs.reload();
    if (event.event_type.startsWith("camera.")) cameras.reload();
    analytics.reload();
  });

  const located = (incidents.data ?? []).filter((incident) => incident.location);
  const points = [
    ...located.map((incident) => ({
      id: incident.id,
      latitude: incident.location!.latitude,
      longitude: incident.location!.longitude,
      label: `${humanise(incident.incident_type)} · ${incident.severity ?? "severity unset"}`,
      detail: `${incident.review_status.replace(/_/g, " ")} · ${formatDateTime(incident.event_time)}`,
      layer:
        incident.review_status === "confirmed"
          ? "confirmed_observation"
          : incident.review_status === "pending"
            ? "pending_candidate"
            : "event",
    })),
    ...(cameras.data ?? [])
      .filter((camera) => camera.location)
      .map((camera) => ({
        id: camera.id,
        latitude: camera.location!.latitude,
        longitude: camera.location!.longitude,
        label: `${camera.camera_code} · ${camera.name}`,
        detail: camera.connection_status.replace(/_/g, " "),
        layer: "camera",
      })),
  ];

  return (
    <>
      <PageHeader
        title={`Operations overview${session ? ` — ${session.user.organization.city ?? session.user.organization.name}` : ""}`}
        description="Everything below is a candidate observation until a reviewer confirms it. Historical accident records are kept separate from AI events."
        tone="command"
        actions={
          <>
            <Link
              href="/command/videos"
              className="rounded-lg bg-sky-500 px-3 py-1.5 text-sm font-medium text-slate-950 hover:bg-sky-400"
            >
              Upload footage
            </Link>
            <Link
              href="/command/incidents"
              className="rounded-lg border border-[#243449] px-3 py-1.5 text-sm text-slate-200 hover:bg-[#131e2c]"
            >
              Review queue
            </Link>
          </>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          tone="command"
          label="AI candidate events"
          value={analytics.data?.pending_candidates ?? "—"}
          hint="Awaiting human review"
          emphasis="warn"
        />
        <MetricCard
          tone="command"
          label="Human-confirmed"
          value={analytics.data?.confirmed_observations ?? "—"}
          hint="Reviewed and accepted"
        />
        <MetricCard
          tone="command"
          label="Historical accident records"
          value={analytics.data?.historical_accidents_in_window ?? "—"}
          hint="Imported CSV records (separate source)"
        />
        <MetricCard
          tone="command"
          label="Cameras online"
          value={`${(cameras.data ?? []).filter((camera) => camera.connection_status === "online").length}/${(cameras.data ?? []).length || 0}`}
          hint="Reporting online in the registry, not merely enabled"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <MapPanel
            tone="command"
            points={points}
            title="Located events and cameras"
            loading={incidents.loading || cameras.loading}
            height={360}
          />
        </div>
        <div className="space-y-4">
          <Card tone="command">
            <CardHeader title="Source separation" description="Why the counts differ" tone="command" />
            <div className="space-y-2 px-4 py-3 text-sm text-slate-300">
              <p>
                <strong className="text-slate-100">AI events</strong> come from the detection
                pipeline and start as <em>pending</em> candidates.
              </p>
              <p>
                <strong className="text-slate-100">Historical accidents</strong> are imported CSV
                records with their own source reference; they are never merged into AI counts.
              </p>
              <p className="text-xs text-slate-500">{analytics.data?.data_note}</p>
            </div>
          </Card>
          <Card tone="command">
            <CardHeader
              title="Realtime feed"
              description="Server-pushed hints; REST stays authoritative."
              tone="command"
            />
            <div className="px-4 py-3">
              <p className="flex items-center gap-2 text-xs text-slate-400">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    realtime.status === "live"
                      ? "bg-emerald-400"
                      : realtime.status === "blocked"
                        ? "bg-rose-400"
                        : "bg-amber-400"
                  }`}
                />
                {realtime.status === "live"
                  ? "Connected (ticket-authenticated)"
                  : realtime.status === "blocked"
                    ? "Realtime unavailable — data refreshes on navigation"
                    : "Connecting…"}
              </p>
              {realtime.events.length ? (
                <ul className="mt-2 space-y-1 text-xs text-slate-400">
                  {realtime.events.slice(0, 5).map((event) => (
                    <li key={event.event_id}>
                      <span className="text-slate-200">{event.event_type}</span> ·{" "}
                      {formatDateTime(event.occurred_at)}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-xs text-slate-500">
                  No realtime events yet. Uploading footage or reviewing an event appears here.
                </p>
              )}
            </div>
          </Card>
          <Card tone="command">
            <CardHeader title="Recent processing jobs" tone="command" />
            {jobs.loading ? (
              <LoadingRows tone="command" />
            ) : jobs.error ? (
              <ErrorState tone="command" message={jobs.error} onRetry={jobs.reload} />
            ) : (
              <DataTable tone="command" head={["Job", "Status", "Stage"]}>
                {(jobs.data ?? []).map((job) => (
                  <Row key={job.id} tone="command">
                    <td className="px-4 py-2 font-mono text-xs text-slate-400">
                      {job.id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-2">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {job.stage.replace(/_/g, " ")} · {job.progress}%
                    </td>
                  </Row>
                ))}
              </DataTable>
            )}
          </Card>
        </div>
      </div>

      <div className="mt-4">
        <Card tone="command">
          <CardHeader
            title="Latest events"
            description={`${analytics.data?.pending_candidates ?? 0} candidate event(s) still need a review decision`}
            tone="command"
            actions={
              <Link href="/command/incidents" className="text-xs text-sky-300 hover:underline">
                View all →
              </Link>
            }
          />
          {incidents.loading ? (
            <LoadingRows tone="command" />
          ) : incidents.error ? (
            <ErrorState tone="command" message={incidents.error} onRetry={incidents.reload} />
          ) : (
            <DataTable
              tone="command"
              head={["Event", "Review", "Score", "Camera", "When", ""]}
              empty="No events yet — upload a clip to run the pipeline."
            >
              {(incidents.data ?? []).map((incident) => (
                <Row key={incident.id} tone="command">
                  <td className="px-4 py-2">
                    <span className="font-medium text-slate-100">
                      {humanise(incident.incident_type)}
                    </span>
                    <span className="ml-2 rounded bg-[#16222f] px-1.5 py-0.5 text-[10px] uppercase text-slate-400">
                      {incident.source_kind === "ai_detected" ? "AI candidate" : "manual"}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge status={incident.review_status} />
                  </td>
                  <td className="px-4 py-2 tabular-nums text-slate-300">
                    {incident.model_score !== null ? incident.model_score.toFixed(2) : "—"}
                  </td>
                  <td className="px-4 py-2 text-slate-400">{incident.camera_code ?? "—"}</td>
                  <td className="px-4 py-2 text-xs text-slate-400">
                    {formatDateTime(incident.event_time)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <Link
                      href={`/command/incidents/${incident.id}`}
                      className="text-xs text-sky-300 hover:underline"
                    >
                      Open
                    </Link>
                  </td>
                </Row>
              ))}
            </DataTable>
          )}
        </Card>
      </div>
    </>
  );
}
