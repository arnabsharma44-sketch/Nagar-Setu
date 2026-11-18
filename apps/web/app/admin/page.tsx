"use client";

import Link from "next/link";
import { useApi } from "@/lib/useApi";
import {
  Card,
  CardHeader,
  DataTable,
  LoadingRows,
  MetricCard,
  PageHeader,
  Row,
  StatusBadge,
} from "@/components/ui";
import { formatDateTime, humanise } from "@/lib/format";
import type {
  Asset,
  AuditEntry,
  Contract,
  Contractor,
  Department,
  IncidentAnalytics,
  Investigation,
  WorkOrder,
} from "@/lib/types";

export default function AdminOverviewPage() {
  const departments = useApi<Department[]>("/api/v1/departments?limit=100");
  const contractors = useApi<Contractor[]>("/api/v1/contractors?limit=100");
  const assets = useApi<Asset[]>("/api/v1/assets?limit=100");
  const contracts = useApi<Contract[]>("/api/v1/contracts?limit=100");
  const investigations = useApi<Investigation[]>("/api/v1/investigations?limit=100");
  const workOrders = useApi<WorkOrder[]>("/api/v1/work-orders?limit=100");
  const analytics = useApi<IncidentAnalytics>("/api/v1/incidents/analytics");
  const audit = useApi<AuditEntry[]>("/api/v1/audit-logs?limit=8");

  const openWorkOrders = (workOrders.data ?? []).filter(
    (order) => !["verified", "cancelled", "rejected"].includes(order.status),
  ).length;
  const awaitingVerification = (workOrders.data ?? []).filter(
    (order) => order.status === "completed_pending_verification",
  ).length;

  return (
    <>
      <PageHeader
        title="Administrative portal"
        description="Registry data, contracts and corrective actions. Every record here is demo data unless it was entered by your organization."
        tone="admin"
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard tone="admin" label="Departments" value={departments.data?.length ?? "—"} hint="Registry entries" />
        <MetricCard tone="admin" label="Assets" value={assets.data?.length ?? "—"} hint={`${(assets.data ?? []).filter((asset) => !asset.department_id).length} without an owning department`} />
        <MetricCard tone="admin" label="Contracts" value={contracts.data?.length ?? "—"} hint={`${contractors.data?.length ?? 0} contractors`} />
        <MetricCard tone="admin" label="Open work orders" value={openWorkOrders} hint={`${awaitingVerification} awaiting verification`} emphasis={awaitingVerification ? "warn" : "default"} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card tone="admin" className="lg:col-span-2">
          <CardHeader
            title="Corrective action pipeline"
            tone="admin"
            actions={
              <Link href="/admin/work-orders" className="text-xs text-blue-700 hover:underline">
                All work orders →
              </Link>
            }
          />
          {workOrders.loading ? (
            <LoadingRows tone="admin" />
          ) : (
            <DataTable
              tone="admin"
              head={["Work order", "Department", "Status", "Priority", "Due", ""]}
              empty="No work orders raised yet."
            >
              {(workOrders.data ?? []).slice(0, 8).map((order) => (
                <Row key={order.id} tone="admin">
                  <td className="px-4 py-2 font-mono text-xs text-slate-700">{order.work_order_number}</td>
                  <td className="px-4 py-2 text-slate-700">{order.department_name ?? "—"}</td>
                  <td className="px-4 py-2">
                    <StatusBadge status={order.status} />
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-500">{humanise(order.priority)}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{formatDateTime(order.due_date)}</td>
                  <td className="px-4 py-2 text-right">
                    <Link href={`/admin/work-orders/${order.id}`} className="text-xs text-blue-700 hover:underline">
                      Open
                    </Link>
                  </td>
                </Row>
              ))}
            </DataTable>
          )}
        </Card>

        <Card tone="admin">
          <CardHeader title="Data quality" description="Registry gaps affect investigation quality." tone="admin" />
          <ul className="space-y-2 px-4 py-3 text-sm text-slate-700">
            <li className="flex justify-between gap-3">
              <span>Assets without coordinates</span>
              <span className="tabular-nums font-medium">
                {(assets.data ?? []).filter((asset) => !asset.location).length}
              </span>
            </li>
            <li className="flex justify-between gap-3">
              <span>Assets without a department</span>
              <span className="tabular-nums font-medium">
                {(assets.data ?? []).filter((asset) => !asset.department_id).length}
              </span>
            </li>
            <li className="flex justify-between gap-3">
              <span>Contracts with no assets linked</span>
              <span className="tabular-nums font-medium">
                {(contracts.data ?? []).filter((contract) => contract.asset_ids.length === 0).length}
              </span>
            </li>
            <li className="flex justify-between gap-3">
              <span>Investigations open</span>
              <span className="tabular-nums font-medium">
                {(investigations.data ?? []).filter((item) => item.status !== "closed").length}
              </span>
            </li>
            <li className="flex justify-between gap-3">
              <span>Candidate events pending review</span>
              <span className="tabular-nums font-medium">{analytics.data?.pending_candidates ?? 0}</span>
            </li>
          </ul>
        </Card>
      </div>

      <div className="mt-4">
        <Card tone="admin">
          <CardHeader
            title="Recent administrative actions"
            description="Consequential actions are audited and cannot be edited."
            tone="admin"
            actions={
              <Link href="/admin/audit-logs" className="text-xs text-blue-700 hover:underline">
                Full audit trail →
              </Link>
            }
          />
          {audit.loading ? (
            <LoadingRows tone="admin" />
          ) : (
            <DataTable tone="admin" head={["Action", "Entity", "Actor", "When"]} empty="No audit entries yet.">
              {(audit.data ?? []).map((entry) => (
                <Row key={entry.id} tone="admin">
                  <td className="px-4 py-2 font-mono text-xs text-slate-700">{entry.action}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">
                    {entry.entity_type}
                    {entry.entity_id ? ` · ${entry.entity_id.slice(0, 8)}` : ""}
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-500">{entry.actor_label ?? "system"}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{formatDateTime(entry.created_at)}</td>
                </Row>
              ))}
            </DataTable>
          )}
        </Card>
      </div>
    </>
  );
}
