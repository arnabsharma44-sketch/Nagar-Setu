"use client";

import Link from "next/link";
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
  StatusBadge,
} from "@/components/ui";
import { formatDateTime, humanise } from "@/lib/format";
import type { Investigation } from "@/lib/types";

export default function InvestigationsPage() {
  const { has } = useSession();
  const investigations = useApi<Investigation[]>("/api/v1/investigations?limit=50");

  if (!has("investigation:read")) return <PermissionNotice tone="command" permission="investigation:read" />;

  return (
    <>
      <PageHeader
        title="Investigations"
        description="Each case links a reviewed observation to an infrastructure asset. Root causes stay hypotheses until a human corroborates them with records."
        tone="command"
      />
      <Card tone="command">
        <CardHeader title="Open cases" description="Ordered by most recently updated." tone="command" />
        {investigations.loading ? (
          <LoadingRows tone="command" />
        ) : investigations.error ? (
          <ErrorState tone="command" message={investigations.error} onRetry={investigations.reload} />
        ) : (
          <DataTable
            tone="command"
            head={["Case", "Title", "Status", "Responsibility", "Hypotheses", "Updated", ""]}
            empty="No investigations yet. Open one from a reviewed event."
          >
            {(investigations.data ?? []).map((investigation) => (
              <Row key={investigation.id} tone="command">
                <td className="px-4 py-2 font-mono text-xs text-slate-300">{investigation.case_number}</td>
                <td className="px-4 py-2 text-slate-100">{investigation.title}</td>
                <td className="px-4 py-2">
                  <StatusBadge status={investigation.status} />
                </td>
                <td className="px-4 py-2 text-xs text-slate-400">
                  {humanise(investigation.responsibility_status)}
                </td>
                <td className="px-4 py-2 tabular-nums text-slate-300">{investigation.hypotheses.length}</td>
                <td className="px-4 py-2 text-xs text-slate-400">{formatDateTime(investigation.updated_at)}</td>
                <td className="px-4 py-2 text-right">
                  <Link href={`/command/investigations/${investigation.id}`} className="text-xs text-sky-300 hover:underline">
                    Open
                  </Link>
                </td>
              </Row>
            ))}
          </DataTable>
        )}
      </Card>
    </>
  );
}
