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
  Textarea,
} from "@/components/ui";
import { formatDate, humanise } from "@/lib/format";
import type { Asset, Contract, Contractor, Department } from "@/lib/types";

export default function ContractsPage() {
  const { has } = useSession();
  const contracts = useApi<Contract[]>("/api/v1/contracts?limit=100");
  const contractors = useApi<Contractor[]>("/api/v1/contractors?limit=100");
  const departments = useApi<Department[]>("/api/v1/departments?limit=100");
  const assets = useApi<Asset[]>("/api/v1/assets?limit=100");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);

  if (!has("registry:read")) return <PermissionNotice tone="admin" permission="registry:read" />;

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await api.post<Contract>("/api/v1/contracts", {
        contractor_id: form.get("contractor_id"),
        department_id: form.get("department_id"),
        contract_number: form.get("contract_number"),
        contract_type: form.get("contract_type"),
        scope_description: form.get("scope_description"),
        start_date: form.get("start_date"),
        end_date: form.get("end_date"),
        warranty_end_date: form.get("warranty_end_date") || null,
        asset_ids: selectedAssets,
        source_reference: form.get("source_reference") || null,
      });
      setOpen(false);
      setSelectedAssets([]);
      contracts.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the contract.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Maintenance contracts"
        description="Contracts record who is responsible for which asset over which dates. A contract that ended before the event date is reported as not active — never as current responsibility."
        tone="admin"
        actions={
          has("registry:manage") ? (
            <Button tone="admin" onClick={() => setOpen((value) => !value)}>
              {open ? "Close" : "Add contract"}
            </Button>
          ) : null
        }
      />

      {error ? (
        <p role="alert" className="mb-3 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {error}
        </p>
      ) : null}

      {open ? (
        <Card tone="admin" className="mb-4">
          <CardHeader title="New contract" tone="admin" />
          <form onSubmit={create} className="grid gap-3 px-4 py-4 sm:grid-cols-2">
            <Field label="Contract number" tone="admin" htmlFor="contract_number">
              <Input tone="admin" id="contract_number" name="contract_number" required minLength={2} />
            </Field>
            <Field label="Contract type" tone="admin" htmlFor="contract_type" hint="e.g. maintenance, construction, warranty">
              <Input tone="admin" id="contract_type" name="contract_type" required minLength={2} defaultValue="maintenance" />
            </Field>
            <Field label="Contractor" tone="admin" htmlFor="contractor_id">
              <select
                id="contractor_id"
                name="contractor_id"
                required
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                <option value="">Select a contractor</option>
                {(contractors.data ?? []).map((contractor) => (
                  <option key={contractor.id} value={contractor.id}>
                    {contractor.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Department" tone="admin" htmlFor="department_id">
              <select
                id="department_id"
                name="department_id"
                required
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                <option value="">Select a department</option>
                {(departments.data ?? []).map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Start date" tone="admin" htmlFor="start_date">
              <Input tone="admin" id="start_date" name="start_date" type="date" required />
            </Field>
            <Field label="End date" tone="admin" htmlFor="end_date">
              <Input tone="admin" id="end_date" name="end_date" type="date" required />
            </Field>
            <Field label="Warranty end (optional)" tone="admin" htmlFor="warranty_end_date">
              <Input tone="admin" id="warranty_end_date" name="warranty_end_date" type="date" />
            </Field>
            <Field label="Source reference" tone="admin" htmlFor="source_reference">
              <Input tone="admin" id="source_reference" name="source_reference" />
            </Field>
            <div className="sm:col-span-2">
              <Field label="Scope description" tone="admin" htmlFor="scope_description">
                <Textarea tone="admin" id="scope_description" name="scope_description" rows={2} required minLength={2} />
              </Field>
            </div>
            <div className="sm:col-span-2">
              <p className="mb-1 text-sm font-medium text-slate-900">Covered assets</p>
              <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
                {(assets.data ?? []).map((asset) => (
                  <label key={asset.id} className="flex items-center gap-2 text-xs text-slate-700">
                    <input
                      type="checkbox"
                      checked={selectedAssets.includes(asset.id)}
                      onChange={(event) =>
                        setSelectedAssets((current) =>
                          event.target.checked
                            ? [...current, asset.id]
                            : current.filter((id) => id !== asset.id),
                        )
                      }
                    />
                    {asset.asset_code} — {asset.name}
                  </label>
                ))}
              </div>
            </div>
            <div className="sm:col-span-2">
              <Button tone="admin" type="submit" disabled={busy}>
                {busy ? "Saving…" : "Save contract"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card tone="admin">
        <CardHeader title="All contracts" tone="admin" />
        {contracts.loading ? (
          <LoadingRows tone="admin" />
        ) : contracts.error ? (
          <ErrorState tone="admin" message={contracts.error} onRetry={contracts.reload} />
        ) : (
          <DataTable
            tone="admin"
            head={["Number", "Contractor", "Department", "Type", "Period", "Assets", "Demo"]}
            empty="No contracts recorded."
          >
            {(contracts.data ?? []).map((contract) => (
              <Row key={contract.id} tone="admin">
                <td className="px-4 py-2 font-mono text-xs text-slate-700">{contract.contract_number}</td>
                <td className="px-4 py-2 text-slate-900">{contract.contractor_name ?? "—"}</td>
                <td className="px-4 py-2 text-xs text-slate-500">{contract.department_name ?? "—"}</td>
                <td className="px-4 py-2 text-xs text-slate-500">{humanise(contract.contract_type)}</td>
                <td className="px-4 py-2 text-xs text-slate-500">
                  {formatDate(contract.start_date)} → {formatDate(contract.end_date)}
                </td>
                <td className="px-4 py-2 text-xs tabular-nums text-slate-500">{contract.asset_ids.length}</td>
                <td className="px-4 py-2 text-xs text-slate-500">{contract.is_demo ? "DEMO" : "—"}</td>
              </Row>
            ))}
          </DataTable>
        )}
      </Card>
    </>
  );
}
