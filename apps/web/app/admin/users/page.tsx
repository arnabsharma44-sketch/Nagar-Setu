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
import { formatDateTime, humanise } from "@/lib/format";
import type { AdminUser, Department } from "@/lib/types";

export default function UsersPage() {
  const { has, meta } = useSession();
  const users = useApi<AdminUser[]>("/api/v1/users?limit=100");
  const departments = useApi<Department[]>("/api/v1/departments?limit=100");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (!has("user:read")) return <PermissionNotice tone="admin" permission="user:read" />;

  const roles = meta?.roles ?? [];

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.post<AdminUser>("/api/v1/users", {
        full_name: form.get("full_name"),
        email: form.get("email"),
        role: form.get("role"),
        department_id: form.get("department_id") || null,
        password: form.get("password"),
      });
      setOpen(false);
      setNotice("User created. They must change the initial password after signing in.");
      users.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the user.");
    } finally {
      setBusy(false);
    }
  }

  async function update(user: AdminUser, patch: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      await api.patch(`/api/v1/users/${user.id}`, patch);
      users.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update the user.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Users and roles"
        description="Roles are assigned here, on the server. A user can never choose their own role or organization at sign-in."
        tone="admin"
        actions={
          has("user:manage") ? (
            <Button tone="admin" onClick={() => setOpen((value) => !value)}>
              {open ? "Close" : "Invite user"}
            </Button>
          ) : null
        }
      />

      {notice ? (
        <p className="mb-3 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{notice}</p>
      ) : null}
      {error ? (
        <p role="alert" className="mb-3 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800">{error}</p>
      ) : null}

      {open ? (
        <Card tone="admin" className="mb-4">
          <CardHeader title="New user" tone="admin" />
          <form onSubmit={create} className="grid gap-3 px-4 py-4 sm:grid-cols-2">
            <Field label="Full name" tone="admin" htmlFor="full_name">
              <Input tone="admin" id="full_name" name="full_name" required minLength={2} />
            </Field>
            <Field label="Email" tone="admin" htmlFor="email">
              <Input tone="admin" id="email" name="email" type="email" required />
            </Field>
            <Field label="Role" tone="admin" htmlFor="role" hint="Permissions come from the role map on the server.">
              <select id="role" name="role" required className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
                {roles.map((role) => (
                  <option key={role} value={role}>
                    {humanise(role)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Department (optional)" tone="admin" htmlFor="department_id">
              <select id="department_id" name="department_id" className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
                <option value="">None</option>
                {(departments.data ?? []).map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Initial password" tone="admin" htmlFor="password" hint="Minimum 12 characters. Share it out-of-band.">
              <Input tone="admin" id="password" name="password" type="password" required minLength={12} />
            </Field>
            <div className="sm:col-span-2">
              <Button tone="admin" type="submit" disabled={busy}>
                {busy ? "Saving…" : "Create user"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card tone="admin">
        <CardHeader title="All users" tone="admin" />
        {users.loading ? (
          <LoadingRows tone="admin" />
        ) : users.error ? (
          <ErrorState tone="admin" message={users.error} onRetry={users.reload} />
        ) : (
          <DataTable tone="admin" head={["Name", "Email", "Role", "Department", "State", "Last sign-in", ""]} empty="No users recorded.">
            {(users.data ?? []).map((user) => (
              <Row key={user.id} tone="admin">
                <td className="px-4 py-2 text-slate-900">{user.full_name}</td>
                <td className="px-4 py-2 text-xs text-slate-600">{user.email}</td>
                <td className="px-4 py-2 text-xs text-slate-600">{humanise(user.role)}</td>
                <td className="px-4 py-2 text-xs text-slate-500">
                  {departments.data?.find((department) => department.id === user.department_id)?.name ?? "—"}
                </td>
                <td className="px-4 py-2">
                  <StatusBadge status={user.is_active ? "active" : "offline"} label={user.is_active ? "Active" : "Disabled"} />
                </td>
                <td className="px-4 py-2 text-xs text-slate-500">{formatDateTime(user.last_login_at)}</td>
                <td className="px-4 py-2 text-right">
                  {has("user:manage") ? (
                    <button
                      type="button"
                      className="text-xs text-blue-700 hover:underline"
                      disabled={busy}
                      onClick={() => void update(user, { is_active: !user.is_active })}
                    >
                      {user.is_active ? "Disable" : "Enable"}
                    </button>
                  ) : null}
                </td>
              </Row>
            ))}
          </DataTable>
        )}
      </Card>
    </>
  );
}
