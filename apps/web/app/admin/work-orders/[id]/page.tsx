"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/useApi";
import { api, ApiError } from "@/lib/api";
import { EvidenceGrid } from "@/components/EvidenceGrid";
import {
  Button,
  Card,
  CardHeader,
  DataTable,
  ErrorState,
  Field,
  Input,
  KeyValue,
  LoadingRows,
  PageHeader,
  PermissionNotice,
  Row,
  StatusBadge,
  Textarea,
} from "@/components/ui";
import { formatBytes, formatDate, formatDateTime, humanise } from "@/lib/format";
import type { Evidence, WorkOrderDetail } from "@/lib/types";

export default function WorkOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const { has } = useSession();
  const detail = useApi<WorkOrderDetail>(`/api/v1/work-orders/${params.id}`);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [evidenceIds, setEvidenceIds] = useState<string[]>([]);

  if (!has("work_order:read")) return <PermissionNotice tone="admin" permission="work_order:read" />;
  if (detail.loading) return <LoadingRows tone="admin" label="Loading work order…" />;
  if (detail.error) return <ErrorState tone="admin" message={detail.error} onRetry={detail.reload} />;
  if (!detail.data) return <ErrorState tone="admin" message="Work order not found." />;

  const order = detail.data;

  async function transition(status: string, note: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.patch(`/api/v1/work-orders/${params.id}`, { status, note });
      setNotice(`Status changed to ${humanise(status)}.`);
      detail.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The status change was rejected.");
    } finally {
      setBusy(false);
    }
  }

  async function uploadEvidence(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = form.get("file");
    if (!(file instanceof File) || !file.size) {
      setError("Choose a file to attach.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload = new FormData();
      payload.append("file", file);
      payload.append("label", String(form.get("label") ?? "Completion evidence"));
      await api.form<Evidence>(`/api/v1/work-orders/${params.id}/evidence`, payload);
      setNotice("Evidence attached. Select it below when you submit completion.");
      detail.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The evidence upload failed.");
    } finally {
      setBusy(false);
    }
  }

  async function submitCompletion(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/v1/work-orders/${params.id}/completion`, {
        completion_notes: form.get("completion_notes"),
        evidence_ids: evidenceIds,
      });
      setNotice("Completion submitted. A different user must verify it.");
      setEvidenceIds([]);
      detail.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Completion could not be submitted.");
    } finally {
      setBusy(false);
    }
  }

  async function verify(status: string) {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/v1/work-orders/${params.id}/verifications`, {
        verification_status: status,
        notes:
          status === "accepted"
            ? "Evidence checked against the work description; accepted."
            : "Evidence does not demonstrate the work was done; returned to the department.",
      });
      setNotice(`Verification recorded as ${humanise(status)}.`);
      detail.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The verification was rejected.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        tone="admin"
        breadcrumb={{ label: "Work orders", href: "/admin/work-orders" }}
        title={`${order.work_order_number} — ${order.title}`}
        description={order.description}
        actions={<StatusBadge status={order.status} />}
      />

      {notice ? (
        <p className="mb-3 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mb-3 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {error}
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card tone="admin">
            <CardHeader title="Work details" tone="admin" />
            <div className="px-4 py-4">
              <KeyValue
                tone="admin"
                items={[
                  ["Department", order.department_name ?? "—"],
                  ["Priority", humanise(order.priority)],
                  ["Due date", formatDate(order.due_date)],
                  ["Created", formatDateTime(order.created_at)],
                  ["Completed", formatDateTime(order.completed_at)],
                  ["Verified", formatDateTime(order.verified_at)],
                  ["Separation of duties", order.separation_of_duties ? "Enforced" : "Not enforced"],
                ]}
              />
              {order.completion_notes ? (
                <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Completion notes</p>
                  {order.completion_notes}
                </div>
              ) : null}
            </div>
          </Card>

          <Card tone="admin">
            <CardHeader title="Evidence" description="Files uploaded against this work order." tone="admin" />
            {order.evidence.length ? (
              <EvidenceGrid items={order.evidence} />
            ) : (
              <p className="px-4 py-6 text-sm text-slate-500">No evidence attached yet.</p>
            )}
          </Card>

          <Card tone="admin">
            <CardHeader title="Status history" tone="admin" />
            {order.history.length ? (
              <DataTable tone="admin" head={["From", "To", "Note", "When"]}>
                {order.history.map((entry) => (
                  <Row key={entry.id} tone="admin">
                    <td className="px-4 py-2 text-xs text-slate-500">{humanise(entry.from_status)}</td>
                    <td className="px-4 py-2">
                      <StatusBadge status={entry.to_status} />
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-600">{entry.note ?? "—"}</td>
                    <td className="px-4 py-2 text-xs text-slate-500">{formatDateTime(entry.created_at)}</td>
                  </Row>
                ))}
              </DataTable>
            ) : (
              <p className="px-4 py-6 text-sm text-slate-500">No transitions recorded.</p>
            )}
          </Card>
        </div>

        <div className="space-y-4">
          <Card tone="admin">
            <CardHeader title="Allowed transitions" tone="admin" />
            <div className="flex flex-wrap gap-2 px-4 py-3">
              {order.allowed_transitions.length ? (
                order.allowed_transitions.map((status) => (
                  <Button key={status} tone="admin" variant="secondary" onClick={() => void transition(status, `Moved to ${humanise(status)} from the admin portal.`)} disabled={busy}>
                    {humanise(status)}
                  </Button>
                ))
              ) : (
                <p className="text-sm text-slate-500">
                  No transitions available from this state for your role.
                </p>
              )}
            </div>
          </Card>

          {order.can_submit_completion ? (
            <Card tone="admin">
              <CardHeader title="Submit completion" description="Attach evidence, then submit for verification." tone="admin" />
              <form onSubmit={uploadEvidence} className="space-y-2 px-4 py-3">
                <Field label="Attach evidence file" tone="admin" htmlFor="file">
                  <Input tone="admin" id="file" name="file" type="file" accept="image/*,video/*,application/pdf" />
                </Field>
                <Field label="Label" tone="admin" htmlFor="label">
                  <Input tone="admin" id="label" name="label" defaultValue="Completion photo" />
                </Field>
                <Button tone="admin" type="submit" variant="secondary" disabled={busy}>
                  Upload evidence
                </Button>
              </form>
              <form onSubmit={submitCompletion} className="space-y-2 border-t border-slate-200 px-4 py-3">
                <Field label="Completion notes" tone="admin" htmlFor="completion_notes" hint="Describe the work performed.">
                  <Textarea tone="admin" id="completion_notes" name="completion_notes" rows={3} required minLength={5} />
                </Field>
                <fieldset>
                  <legend className="mb-1 text-sm font-medium text-slate-900">Evidence to submit</legend>
                  {order.evidence.length ? (
                    order.evidence.map((item) => (
                      <label key={item.id} className="flex items-center gap-2 text-xs text-slate-700">
                        <input
                          type="checkbox"
                          checked={evidenceIds.includes(item.id)}
                          onChange={(event) =>
                            setEvidenceIds((current) =>
                              event.target.checked
                                ? [...current, item.id]
                                : current.filter((id) => id !== item.id),
                            )
                          }
                        />
                        {item.label ?? humanise(item.evidence_type)} · {formatBytes(item.file_size_bytes)}
                      </label>
                    ))
                  ) : (
                    <p className="text-xs text-slate-500">Upload at least one file first.</p>
                  )}
                </fieldset>
                <Button tone="admin" type="submit" disabled={busy}>
                  Submit for verification
                </Button>
              </form>
            </Card>
          ) : null}

          {order.can_verify ? (
            <Card tone="admin">
              <CardHeader title="Verification" description="Only a user who did not complete the work may verify it." tone="admin" />
              <div className="space-y-2 px-4 py-3">
                <Button tone="admin" onClick={() => void verify("accepted")} disabled={busy}>
                  Accept completion
                </Button>
                <Button tone="admin" variant="secondary" onClick={() => void verify("needs_more_evidence")} disabled={busy}>
                  Request more evidence
                </Button>
                <Button tone="admin" variant="danger" onClick={() => void verify("rejected")} disabled={busy}>
                  Reject completion
                </Button>
              </div>
            </Card>
          ) : (
            <Card tone="admin">
              <CardHeader title="Verification" tone="admin" />
              <p className="px-4 py-3 text-sm text-slate-500">
                {order.status === "completed_pending_verification"
                  ? "You cannot verify this completion (separation of duties, or your role lacks the permission)."
                  : "Verification opens once the department submits completion evidence."}
              </p>
            </Card>
          )}

          {order.verifications.length ? (
            <Card tone="admin">
              <CardHeader title="Verification records" tone="admin" />
              <ul className="space-y-2 px-4 py-3 text-sm">
                {order.verifications.map((verification) => (
                  <li key={verification.id} className="rounded-lg border border-slate-200 px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <StatusBadge status={verification.verification_status} />
                      <span className="text-xs text-slate-500">{formatDateTime(verification.verified_at)}</span>
                    </div>
                    <p className="mt-1 text-slate-700">{verification.notes}</p>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
        </div>
      </div>
    </>
  );
}
