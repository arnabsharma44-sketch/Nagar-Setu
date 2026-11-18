"use client";

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
  PermissionNotice,
  Row,
  StatusBadge,
} from "@/components/ui";
import { formatDateTime, humanise } from "@/lib/format";
import type { AccidentRecord, HotspotAnalysis, IncidentAnalytics } from "@/lib/types";

export default function AdminAnalyticsPage() {
  const { has } = useSession();
  const analytics = useApi<IncidentAnalytics>("/api/v1/incidents/analytics");
  const hotspots = useApi<HotspotAnalysis[]>("/api/v1/hotspots?limit=1");
  const accidents = useApi<AccidentRecord[]>("/api/v1/accident-records?limit=100");

  if (!has("analytics:read")) return <PermissionNotice tone="admin" permission="analytics:read" />;

  const latest = hotspots.data?.[0] ?? null;
  const clusters = latest?.clusters ?? [];
  const points = clusters.map((cluster) => ({
    id: cluster.cluster_key,
    latitude: cluster.latitude,
    longitude: cluster.longitude,
    label: cluster.label,
    detail: `${cluster.total_records} record(s)`,
    layer: "hotspot",
  }));

  return (
    <>
      <PageHeader
        title="Analytics"
        description="Counts are reported with their source. Historical accident records and AI-detected candidates are never summed into a single 'accidents' figure."
        tone="admin"
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard tone="admin" label="All events" value={analytics.data?.total ?? "—"} hint="AI candidates and manual reports" />
        <MetricCard tone="admin" label="Confirmed" value={analytics.data?.confirmed_observations ?? "—"} hint="Human reviewed" />
        <MetricCard tone="admin" label="Pending" value={analytics.data?.pending_candidates ?? "—"} hint="Awaiting review" emphasis="warn" />
        <MetricCard tone="admin" label="Historical records" value={analytics.data?.historical_accidents_in_window ?? "—"} hint="Imported CSV source" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card tone="admin" className="lg:col-span-1">
          <CardHeader title="Event mix" tone="admin" />
          {analytics.loading ? (
            <LoadingRows tone="admin" />
          ) : analytics.error ? (
            <ErrorState tone="admin" message={analytics.error} onRetry={analytics.reload} />
          ) : (
            <div className="space-y-4 px-4 py-4 text-sm">
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">By review state</p>
                <ul className="space-y-1 text-slate-700">
                  {Object.entries(analytics.data?.by_review_status ?? {}).map(([key, value]) => (
                    <li key={key} className="flex justify-between">
                      <span>{humanise(key)}</span>
                      <span className="tabular-nums font-medium">{value}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">By event type</p>
                <ul className="space-y-1 text-slate-700">
                  {Object.entries(analytics.data?.by_type ?? {}).map(([key, value]) => (
                    <li key={key} className="flex justify-between">
                      <span>{humanise(key)}</span>
                      <span className="tabular-nums font-medium">{value}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <p className="text-xs text-slate-500">{analytics.data?.data_note}</p>
            </div>
          )}
        </Card>

        <div className="lg:col-span-2">
          <MapPanel
            tone="admin"
            points={points}
            title="Latest hotspot clusters"
            description={latest ? `${latest.method} · ${latest.radius_meters} m radius` : "No hotspot analysis has been generated yet."}
            loading={hotspots.loading}
            height={340}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-4">
        <Card tone="admin">
          <CardHeader
            title="Clusters"
            description={latest?.methodology_note ?? "Clusters combine located records; they are not exposure-normalised risk rates."}
            tone="admin"
          />
          {hotspots.loading ? (
            <LoadingRows tone="admin" />
          ) : hotspots.error ? (
            <ErrorState tone="admin" message={hotspots.error} onRetry={hotspots.reload} />
          ) : (
            <DataTable tone="admin" head={["Cluster", "Records", "Sources", "First seen", "Last seen"]} empty="No clusters yet.">
              {clusters.map((cluster) => (
                <Row key={cluster.cluster_key} tone="admin">
                  <td className="px-4 py-2 text-slate-900">{cluster.label}</td>
                  <td className="px-4 py-2 tabular-nums text-slate-700">{cluster.total_records}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{cluster.source_mix.join(", ")}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{formatDateTime(cluster.first_seen)}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{formatDateTime(cluster.last_seen)}</td>
                </Row>
              ))}
            </DataTable>
          )}
        </Card>

        <Card tone="admin">
          <CardHeader title="Historical accident records" description="Imported reference data with its own source reference and verification state." tone="admin" />
          {accidents.loading ? (
            <LoadingRows tone="admin" />
          ) : accidents.error ? (
            <ErrorState tone="admin" message={accidents.error} onRetry={accidents.reload} />
          ) : (
            <DataTable
              tone="admin"
              head={["Date", "Road", "Type", "Severity", "Source", "Verification"]}
              empty="No historical records imported."
            >
              {(accidents.data ?? []).slice(0, 25).map((record) => (
                <Row key={record.id} tone="admin">
                  <td className="px-4 py-2 text-xs text-slate-500">{record.accident_date ?? formatDateTime(record.accident_time)}</td>
                  <td className="px-4 py-2 text-slate-800">{record.road_name ?? "—"}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{humanise(record.accident_type)}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{humanise(record.severity)}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{record.source_name}</td>
                  <td className="px-4 py-2">
                    <StatusBadge status={record.verification_status} />
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
