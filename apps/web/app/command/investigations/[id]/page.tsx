"use client";

import Link from "next/link";
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
  KeyValue,
  LoadingRows,
  PageHeader,
  PermissionNotice,
  Row,
  StatusBadge,
  TagList,
  Textarea,
} from "@/components/ui";
import { formatDate, formatDateTime, humanise } from "@/lib/format";
import type {
  Department,
  InvestigationAnalysis,
  InvestigationDetail,
  Recommendation,
  WorkOrder,
} from "@/lib/types";

export default function InvestigationDetailPage() {
  const params = useParams<{ id: string }>();
  const { has, session } = useSession();
  const detail = useApi<InvestigationDetail>(`/api/v1/investigations/${params.id}`);
  const departments = useApi<Department[]>("/api/v1/departments?limit=100");
  const [analysis, setAnalysis] = useState<InvestigationAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showRecommendation, setShowRecommendation] = useState(false);
  const [showWorkOrder, setShowWorkOrder] = useState<{ recommendationId: string | null } | null>(
    null,
  );

  if (!has("investigation:read")) return <PermissionNotice tone="command" permission="investigation:read" />;

  const investigation = detail.data?.investigation;

  async function runAnalysis() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.post<InvestigationAnalysis>(`/api/v1/investigations/${params.id}/analyze`);
      setAnalysis(result);
      setNotice(
        `Draft analysis produced by the ${result.analysis_source} engine. It is a set of hypotheses for a human to verify.`,
      );
      detail.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The analysis could not be produced.");
    } finally {
      setBusy(false);
    }
  }

  async function submitRecommendation(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await api.post<Recommendation>(`/api/v1/investigations/${params.id}/recommendations`, {
        recommendation_text: form.get("recommendation_text"),
        rationale: form.get("rationale"),
        priority: form.get("priority"),
        limitations: [],
      });
      setShowRecommendation(false);
      setNotice("Recommendation drafted. It needs approval by a different user before a work order.");
      detail.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the recommendation.");
    } finally {
      setBusy(false);
    }
  }

  async function reviewRecommendation(id: string, decision: "approved" | "rejected") {
    setBusy(true);
    setError(null);
    try {
      await api.patch(`/api/v1/recommendations/${id}/review`, {
        decision,
        notes: decision === "approved" ? "Approved after reviewing the case evidence." : "Rejected; insufficient support.",
      });
      setNotice(`Recommendation ${decision}.`);
      detail.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not record the approval decision.");
    } finally {
      setBusy(false);
    }
  }

  async function createWorkOrder(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await api.post<WorkOrder>("/api/v1/work-orders", {
        investigation_id: params.id,
        recommendation_id: showWorkOrder?.recommendationId ?? null,
        assigned_department_id: form.get("assigned_department_id"),
        title: form.get("title"),
        description: form.get("description"),
        priority: form.get("priority"),
        due_date: form.get("due_date") || null,
      });
      setShowWorkOrder(null);
      setNotice("Work order created. A department user must accept it, complete the work and submit evidence.");
      detail.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the work order.");
    } finally {
      setBusy(false);
    }
  }

  if (detail.loading) return <LoadingRows tone="command" label="Loading case…" />;
  if (detail.error) return <ErrorState tone="command" message={detail.error} onRetry={detail.reload} />;
  if (!detail.data || !investigation) return <ErrorState tone="command" message="Case not found." />;

  const data = detail.data;
  const responsibility = data.responsibility;
  const hypotheses = analysis?.potential_root_causes ?? investigation.hypotheses;

  return (
    <>
      <PageHeader
        tone="command"
        breadcrumb={{ label: "Investigations", href: "/command/investigations" }}
        title={`${investigation.case_number} — ${investigation.title}`}
        description={investigation.summary ?? undefined}
        actions={
          <>
            <StatusBadge status={investigation.status} />
            {has("investigation:analyze") ? (
              <Button tone="command" variant="secondary" onClick={() => void runAnalysis()} disabled={busy}>
                {busy ? "Working…" : "Draft analysis"}
              </Button>
            ) : null}
          </>
        }
      />

      {notice ? (
        <p className="mb-3 rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-sm text-sky-200">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mb-3 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card tone="command">
            <CardHeader
              title="Infrastructure record match"
              description="Nearest registered asset within the match radius. Records only — not a liability conclusion."
              tone="command"
            />
            <div className="px-4 py-4">
              {responsibility ? (
                <>
                  <KeyValue
                    tone="command"
                    items={[
                      ["Match status", <StatusBadge key="s" status={responsibility.status} />],
                      ["Asset", responsibility.asset_name ? `${responsibility.asset_code} — ${responsibility.asset_name}` : "No match"],
                      ["Owning department", responsibility.owning_department_name ?? "Not recorded"],
                      ["Match method", responsibility.match_method],
                      [
                        "Distance",
                        responsibility.distance_meters !== null
                          ? `${responsibility.distance_meters.toFixed(1)} m from the event location`
                          : "—",
                      ],
                    ]}
                  />
                  <div className="mt-4">
                    <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Contracts</p>
                    {responsibility.contracts.length ? (
                      <ul className="space-y-2 text-sm text-slate-300">
                        {responsibility.contracts.map((contract) => (
                          <li key={contract.contract_id} className="rounded-lg border border-[#1e2b3c] bg-[#0b1320] px-3 py-2">
                            <p className="font-medium text-slate-100">
                              {contract.contract_number} · {contract.contractor_name}
                            </p>
                            <p className="text-xs text-slate-400">
                              {contract.contract_type} · {formatDate(contract.start_date)} →{" "}
                              {formatDate(contract.end_date)} ·{" "}
                              {contract.is_active_on_event_date ? "active on event date" : "not active on event date"}
                            </p>
                            <p className="mt-1 text-xs text-slate-400">{contract.date_note}</p>
                            {contract.scope_notes ? (
                              <p className="mt-1 text-xs text-amber-200/80">{contract.scope_notes}</p>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-slate-500">No contract records cover this asset.</p>
                    )}
                  </div>
                  {responsibility.missing_records.length ? (
                    <div className="mt-3">
                      <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Missing records</p>
                      <TagList tone="command" items={responsibility.missing_records} />
                    </div>
                  ) : null}
                  {responsibility.conflicts.length ? (
                    <div className="mt-3">
                      <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Conflicts</p>
                      <TagList tone="command" items={responsibility.conflicts} />
                    </div>
                  ) : null}
                  <p className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-100/80">
                    {responsibility.disclaimer}
                  </p>
                </>
              ) : (
                <p className="text-sm text-slate-500">
                  This case has no linked asset yet. Record match results appear once an asset is
                  associated.
                </p>
              )}
            </div>
          </Card>

          <Card tone="command">
            <CardHeader
              title="Root-cause hypotheses"
              description={
                analysis
                  ? `${analysis.analysis_source} draft · model ${analysis.model_name ?? "none"}`
                  : "Deterministic drafts are stored with the case. Run an analysis to refresh."
              }
              tone="command"
            />
            <div className="space-y-3 px-4 py-4">
              {hypotheses.length ? (
                hypotheses.map((hypothesis, index) => (
                  <div key={`${hypothesis.hypothesis}-${index}`} className="rounded-lg border border-[#1e2b3c] bg-[#0b1320] px-3 py-2">
                    <p className="text-sm text-slate-100">{hypothesis.hypothesis}</p>
                    <p className="mt-1 text-xs text-slate-400">
                      Confidence label: {hypothesis.confidence_label} · supporting records:{" "}
                      {hypothesis.supporting_record_ids.length || "none"}
                    </p>
                    {hypothesis.counter_evidence.length ? (
                      <p className="mt-1 text-xs text-amber-200/80">
                        Counter-evidence: {hypothesis.counter_evidence.join("; ")}
                      </p>
                    ) : null}
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500">
                  No hypotheses drafted yet. Hypotheses are possibilities to check, not conclusions.
                </p>
              )}
              {analysis ? (
                <>
                  <div>
                    <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Missing information</p>
                    <TagList tone="command" items={analysis.missing_information} />
                  </div>
                  <div>
                    <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Limitations</p>
                    <TagList tone="command" items={analysis.limitations} />
                  </div>
                  <div>
                    <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Likely responsible authorities</p>
                    <TagList tone="command" items={analysis.potentially_relevant_authorities} emptyLabel="Not determined from records" />
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Human verification required: {analysis.human_verification_required ? "yes" : "no"}.
                  </p>
                </>
              ) : null}
            </div>
          </Card>

          <Card tone="command">
            <CardHeader title="Case evidence" description="Artefacts attached to the linked event or uploaded by an investigator." tone="command" />
            {data.evidence.length || data.incident_evidence.length ? (
              <EvidenceGrid items={[...data.evidence, ...data.incident_evidence]} />
            ) : (
              <p className="px-4 py-6 text-sm text-slate-500">No evidence attached to this case.</p>
            )}
          </Card>
        </div>

        <div className="space-y-4">
          <Card tone="command">
            <CardHeader
              title="Recommendations"
              tone="command"
              actions={
                has("recommendation:create") ? (
                  <Button tone="command" variant="secondary" onClick={() => setShowRecommendation((value) => !value)}>
                    {showRecommendation ? "Close" : "Draft"}
                  </Button>
                ) : null
              }
            />
            <div className="space-y-3 px-4 py-4">
              {showRecommendation ? (
                <form onSubmit={submitRecommendation} className="space-y-2 rounded-lg border border-[#1e2b3c] bg-[#0b1320] p-3">
                  <Field label="Recommendation" tone="command" htmlFor="recommendation_text">
                    <Textarea tone="command" id="recommendation_text" name="recommendation_text" rows={3} required minLength={5} />
                  </Field>
                  <Field label="Rationale" tone="command" htmlFor="rationale">
                    <Textarea tone="command" id="rationale" name="rationale" rows={2} required minLength={5} />
                  </Field>
                  <Field label="Priority" tone="command" htmlFor="priority">
                    <select
                      id="priority"
                      name="priority"
                      className="w-full rounded-lg border border-[#243449] bg-[#0b1320] px-3 py-2 text-sm text-slate-100"
                    >
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                    </select>
                  </Field>
                  <Button tone="command" type="submit" disabled={busy}>
                    Save draft
                  </Button>
                </form>
              ) : null}

              {data.recommendations.length ? (
                <ul className="space-y-2">
                  {data.recommendations.map((recommendation) => (
                    <li key={recommendation.id} className="rounded-lg border border-[#1e2b3c] bg-[#0b1320] px-3 py-2">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm text-slate-100">{recommendation.recommendation_text}</p>
                        <StatusBadge status={recommendation.status} />
                      </div>
                      <p className="mt-1 text-xs text-slate-400">{recommendation.rationale}</p>
                      <p className="mt-1 text-[11px] text-slate-500">
                        Priority {recommendation.priority} · created {formatDateTime(recommendation.created_at)}
                      </p>
                      {recommendation.status === "draft" && has("recommendation:approve") ? (
                        <div className="mt-2 flex gap-2">
                          <Button
                            tone="command"
                            onClick={() => void reviewRecommendation(recommendation.id, "approved")}
                            disabled={busy}
                          >
                            Approve
                          </Button>
                          <Button
                            tone="command"
                            variant="secondary"
                            onClick={() => void reviewRecommendation(recommendation.id, "rejected")}
                            disabled={busy}
                          >
                            Reject
                          </Button>
                        </div>
                      ) : null}
                      {recommendation.status === "approved" && has("work_order:create") ? (
                        <Button
                          tone="command"
                          variant="secondary"
                          className="mt-2"
                          onClick={() => setShowWorkOrder({ recommendationId: recommendation.id })}
                        >
                          Create work order
                        </Button>
                      ) : null}
                      {recommendation.created_by === session?.user.id &&
                      recommendation.status === "draft" ? (
                        <p className="mt-1 text-[11px] text-amber-200/80">
                          You drafted this. A different user must approve it.
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No recommendations drafted.</p>
              )}
            </div>
          </Card>

          <Card tone="command">
            <CardHeader
              title="Work orders"
              tone="command"
              actions={
                has("work_order:create") && !showWorkOrder ? (
                  <Button tone="command" variant="secondary" onClick={() => setShowWorkOrder({ recommendationId: null })}>
                    New
                  </Button>
                ) : null
              }
            />
            <div className="space-y-3 px-4 py-4">
              {showWorkOrder ? (
                <form onSubmit={createWorkOrder} className="space-y-2 rounded-lg border border-[#1e2b3c] bg-[#0b1320] p-3">
                  <Field label="Department" tone="command" htmlFor="assigned_department_id">
                    <select
                      id="assigned_department_id"
                      name="assigned_department_id"
                      required
                      className="w-full rounded-lg border border-[#243449] bg-[#0b1320] px-3 py-2 text-sm text-slate-100"
                    >
                      <option value="">Select a department</option>
                      {(departments.data ?? []).map((department) => (
                        <option key={department.id} value={department.id}>
                          {department.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Title" tone="command" htmlFor="title">
                    <Textarea tone="command" id="title" name="title" rows={1} required minLength={4} />
                  </Field>
                  <Field label="Description" tone="command" htmlFor="description">
                    <Textarea tone="command" id="description" name="description" rows={3} required minLength={5} />
                  </Field>
                  <Field label="Due date" tone="command" htmlFor="due_date">
                    <Textarea tone="command" id="due_date" name="due_date" rows={1} placeholder="YYYY-MM-DD" />
                  </Field>
                  <Button tone="command" type="submit" disabled={busy}>
                    Create work order
                  </Button>
                  <p className="text-[11px] text-slate-500">
                    The department must accept, complete and attach evidence; a different user then
                    verifies it.
                  </p>
                </form>
              ) : null}

              {data.work_orders.length ? (
                <DataTable tone="command" head={["WO", "Status", "Priority"]}>
                  {data.work_orders.map((workOrder) => (
                    <Row key={workOrder.id} tone="command">
                      <td className="px-3 py-2">
                        <Link href={`/admin/work-orders/${workOrder.id}`} className="font-mono text-xs text-sky-300 hover:underline">
                          {workOrder.work_order_number}
                        </Link>
                      </td>
                      <td className="px-3 py-2">
                        <StatusBadge status={workOrder.status} />
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-400">{workOrder.priority}</td>
                    </Row>
                  ))}
                </DataTable>
              ) : (
                <p className="text-sm text-slate-500">No work orders raised from this case.</p>
              )}
            </div>
          </Card>

          <Card tone="command">
            <CardHeader title="Nearby assets" tone="command" />
            <div className="px-4 py-3">
              {data.nearby_assets.length ? (
                <ul className="space-y-1 text-xs text-slate-400">
                  {data.nearby_assets.map((asset) => (
                    <li key={asset.asset_id}>
                      <span className="text-slate-200">{asset.asset_code}</span> · {asset.name} ·{" "}
                      {asset.distance_meters.toFixed(0)} m
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No registered assets nearby.</p>
              )}
              {data.source_records.length ? (
                <p className="mt-3 text-[11px] text-slate-500">
                  Source records: {data.source_records.join(", ")}.
                </p>
              ) : null}
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
