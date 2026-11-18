"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/useApi";
import {
  Card,
  CardHeader,
  DataTable,
  ErrorState,
  KeyValue,
  LoadingRows,
  PageHeader,
  PermissionNotice,
  Row,
  StatusBadge,
  TagList,
} from "@/components/ui";
import { formatDate, formatDateTime, humanise } from "@/lib/format";
import type { InvestigationDetail } from "@/lib/types";

export default function AdminInvestigationDetailPage() {
  const params = useParams<{ id: string }>();
  const { has } = useSession();
  const detail = useApi<InvestigationDetail>(`/api/v1/investigations/${params.id}`);

  if (!has("investigation:read")) return <PermissionNotice tone="admin" permission="investigation:read" />;
  if (detail.loading) return <LoadingRows tone="admin" label="Loading case…" />;
  if (detail.error) return <ErrorState tone="admin" message={detail.error} onRetry={detail.reload} />;
  if (!detail.data) return <ErrorState tone="admin" message="Case not found." />;

  const { investigation, responsibility, recommendations, work_orders: workOrders } = detail.data;

  return (
    <>
      <PageHeader
        tone="admin"
        breadcrumb={{ label: "Case register", href: "/admin/investigations" }}
        title={`${investigation.case_number} — ${investigation.title}`}
        description={investigation.summary ?? undefined}
        actions={<StatusBadge status={investigation.status} />}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card tone="admin">
          <CardHeader title="Record match" description="Derived from the asset registry and contract dates." tone="admin" />
          <div className="px-4 py-4">
            <KeyValue
              tone="admin"
              items={[
                ["Status", <StatusBadge key="status" status={responsibility?.status ?? investigation.responsibility_status} />],
                ["Asset", responsibility?.asset_name ? `${responsibility.asset_code} — ${responsibility.asset_name}` : "No asset matched"],
                ["Owning department", responsibility?.owning_department_name ?? "Not recorded"],
                ["Match method", responsibility?.match_method ?? "—"],
                ["Distance", responsibility?.distance_meters !== null && responsibility?.distance_meters !== undefined ? `${responsibility.distance_meters.toFixed(1)} m` : "—"],
                ["Opened", formatDateTime(investigation.created_at)],
              ]}
            />
            {responsibility?.disclaimer ? (
              <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                {responsibility.disclaimer}
              </p>
            ) : null}
          </div>
        </Card>

        <Card tone="admin">
          <CardHeader title="Contract coverage" tone="admin" />
          <div className="space-y-2 px-4 py-4">
            {responsibility?.contracts.length ? (
              responsibility.contracts.map((contract) => (
                <div key={contract.contract_id} className="rounded-lg border border-slate-200 px-3 py-2">
                  <p className="text-sm font-medium text-slate-900">
                    {contract.contract_number} · {contract.contractor_name}
                  </p>
                  <p className="text-xs text-slate-600">
                    {humanise(contract.contract_type)} · {formatDate(contract.start_date)} →{" "}
                    {formatDate(contract.end_date)}
                  </p>
                  <p className={`mt-1 text-xs ${contract.is_active_on_event_date ? "text-emerald-700" : "text-amber-700"}`}>
                    {contract.is_active_on_event_date ? "Active on the event date" : "Not active on the event date"} —{" "}
                    {contract.date_note}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">No contract records cover this asset.</p>
            )}
            {responsibility?.missing_records.length ? (
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Missing records</p>
                <TagList tone="admin" items={responsibility.missing_records} />
              </div>
            ) : null}
          </div>
        </Card>

        <Card tone="admin">
          <CardHeader title="Hypotheses on file" description="Possibilities to verify with records — not conclusions." tone="admin" />
          <div className="space-y-2 px-4 py-4">
            {investigation.hypotheses.length ? (
              investigation.hypotheses.map((hypothesis, index) => (
                <div key={index} className="rounded-lg border border-slate-200 px-3 py-2">
                  <p className="text-sm text-slate-900">{hypothesis.hypothesis}</p>
                  <p className="text-xs text-slate-500">
                    Confidence {hypothesis.confidence_label} · supporting records{" "}
                    {hypothesis.supporting_record_ids.length}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">No analysis drafted yet.</p>
            )}
          </div>
        </Card>

        <Card tone="admin">
          <CardHeader title="Recommendations and work orders" tone="admin" />
          <div className="px-4 py-4">
            {recommendations.length ? (
              <ul className="mb-3 space-y-2">
                {recommendations.map((recommendation) => (
                  <li key={recommendation.id} className="flex items-start justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2">
                    <span className="text-sm text-slate-800">{recommendation.recommendation_text}</span>
                    <StatusBadge status={recommendation.status} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mb-3 text-sm text-slate-500">No recommendations drafted.</p>
            )}
            {workOrders.length ? (
              <DataTable tone="admin" head={["WO", "Status", "Priority", ""]}>
                {workOrders.map((order) => (
                  <Row key={order.id} tone="admin">
                    <td className="px-3 py-2 font-mono text-xs text-slate-700">{order.work_order_number}</td>
                    <td className="px-3 py-2">
                      <StatusBadge status={order.status} />
                    </td>
                    <td className="px-3 py-2 text-xs text-slate-500">{humanise(order.priority)}</td>
                    <td className="px-3 py-2 text-right">
                      <Link href={`/admin/work-orders/${order.id}`} className="text-xs text-blue-700 hover:underline">
                        Open
                      </Link>
                    </td>
                  </Row>
                ))}
              </DataTable>
            ) : (
              <p className="text-sm text-slate-500">No work orders raised from this case.</p>
            )}
          </div>
        </Card>
      </div>
    </>
  );
}
