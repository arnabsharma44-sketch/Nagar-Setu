"use client";

import { useSession } from "@/lib/session";
import { useApi } from "@/lib/useApi";
import {
  Card,
  CardHeader,
  DataTable,
  ErrorState,
  LoadingRows,
  PageHeader,
  PermissionNotice,
  Row,
} from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import type { AuditEntry } from "@/lib/types";

export default function AuditLogsPage() {
  const { has } = useSession();
  const entries = useApi<AuditEntry[]>("/api/v1/audit-logs?limit=100");

  if (!has("audit:read")) return <PermissionNotice tone="admin" permission="audit:read" />;

  return (
    <>
      <PageHeader
        title="Audit trail"
        description="Append-only record of consequential actions. Entries cannot be edited or deleted by application users."
        tone="admin"
      />
      <Card tone="admin">
        <CardHeader title="Recent entries" description={`${entries.data?.length ?? 0} most recent actions in your organization.`} tone="admin" />
        {entries.loading ? (
          <LoadingRows tone="admin" />
        ) : entries.error ? (
          <ErrorState tone="admin" message={entries.error} onRetry={entries.reload} />
        ) : (
          <DataTable tone="admin" head={["When", "Actor", "Action", "Entity", "Summary", "Request"]} empty="No audit entries recorded yet.">
            {(entries.data ?? []).map((entry) => (
              <Row key={entry.id} tone="admin">
                <td className="whitespace-nowrap px-4 py-2 text-xs text-slate-500">{formatDateTime(entry.created_at)}</td>
                <td className="px-4 py-2 text-xs text-slate-700">{entry.actor_label ?? "system"}</td>
                <td className="px-4 py-2 font-mono text-xs text-slate-800">{entry.action}</td>
                <td className="px-4 py-2 text-xs text-slate-500">
                  {entry.entity_type}
                  {entry.entity_id ? ` · ${entry.entity_id.slice(0, 8)}` : ""}
                </td>
                <td className="px-4 py-2 text-xs text-slate-600">{entry.summary ?? "—"}</td>
                <td className="px-4 py-2 font-mono text-[10px] text-slate-400">
                  {entry.request_id ? entry.request_id.slice(0, 8) : "—"}
                </td>
              </Row>
            ))}
          </DataTable>
        )}
      </Card>
    </>
  );
}
