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
  Textarea,
} from "@/components/ui";
import { formatCoordinates, formatDateTime } from "@/lib/format";
import type { Camera } from "@/lib/types";

export default function CamerasPage() {
  const { has } = useSession();
  const cameras = useApi<Camera[]>("/api/v1/cameras?limit=100");
  const [showForm, setShowForm] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!has("camera:read")) return <PermissionNotice tone="command" permission="camera:read" />;

  async function createCamera(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const latitude = form.get("latitude");
      const longitude = form.get("longitude");
      await api.post<Camera>("/api/v1/cameras", {
        camera_code: form.get("camera_code"),
        name: form.get("name"),
        description: form.get("description") || null,
        source_type: form.get("source_type"),
        location:
          latitude && longitude
            ? { latitude: Number(latitude), longitude: Number(longitude), quality: "approximate" }
            : null,
      });
      setMessage("Camera registered.");
      setShowForm(false);
      cameras.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not register the camera.");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(camera: Camera) {
    setError(null);
    setMessage(null);
    try {
      await api.post(`/api/v1/cameras/${camera.id}/${camera.is_enabled ? "disable" : "enable"}`);
      setMessage(`${camera.camera_code} ${camera.is_enabled ? "disabled" : "enabled"}.`);
      cameras.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change the camera state.");
    }
  }

  return (
    <>
      <PageHeader
        title="Camera registry"
        description="Registered camera positions and connection state. RTSP URLs and credentials are stored only as an external secret reference and never returned to the browser."
        tone="command"
        actions={
          has("camera:manage") ? (
            <Button tone="command" onClick={() => setShowForm((value) => !value)}>
              {showForm ? "Close form" : "Register camera"}
            </Button>
          ) : null
        }
      />

      {message ? (
        <p className="mb-3 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">
          {message}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mb-3 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      ) : null}

      {showForm ? (
        <Card tone="command" className="mb-4">
          <CardHeader title="Register a camera" tone="command" />
          <form onSubmit={createCamera} className="grid gap-3 px-4 py-4 sm:grid-cols-2">
            <Field label="Camera code" tone="command" htmlFor="camera_code">
              <Input tone="command" id="camera_code" name="camera_code" required minLength={2} />
            </Field>
            <Field label="Name" tone="command" htmlFor="name">
              <Input tone="command" id="name" name="name" required minLength={2} />
            </Field>
            <Field label="Source type" tone="command" htmlFor="source_type" hint="RTSP stays disabled in this prototype.">
              <select
                id="source_type"
                name="source_type"
                className="w-full rounded-lg border border-[#243449] bg-[#0b1320] px-3 py-2 text-sm text-slate-100"
              >
                <option value="upload_association">Upload association</option>
                <option value="simulated_live">Simulated live</option>
                <option value="rtsp">RTSP (blocked)</option>
              </select>
            </Field>
            <Field label="Description" tone="command" htmlFor="description">
              <Textarea tone="command" id="description" name="description" rows={2} />
            </Field>
            <Field label="Latitude" tone="command" htmlFor="latitude" hint="Optional. 0 means not surveyed.">
              <Input tone="command" id="latitude" name="latitude" type="number" step="0.00001" />
            </Field>
            <Field label="Longitude" tone="command" htmlFor="longitude">
              <Input tone="command" id="longitude" name="longitude" type="number" step="0.00001" />
            </Field>
            <div className="sm:col-span-2">
              <Button tone="command" type="submit" disabled={busy}>
                {busy ? "Saving…" : "Save camera"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card tone="command">
        <CardHeader title="All cameras" description="Coordinates shown only where a survey value exists." tone="command" />
        {cameras.loading ? (
          <LoadingRows tone="command" />
        ) : cameras.error ? (
          <ErrorState tone="command" message={cameras.error} onRetry={cameras.reload} />
        ) : (
          <DataTable
            tone="command"
            head={["Code", "Name", "Source", "Connection", "Location", "Last seen", "Enabled", ""]}
            empty="No cameras registered yet."
          >
            {(cameras.data ?? []).map((camera) => (
              <Row key={camera.id} tone="command">
                <td className="px-4 py-2 font-mono text-xs text-slate-300">{camera.camera_code}</td>
                <td className="px-4 py-2 text-slate-100">{camera.name}</td>
                <td className="px-4 py-2 text-xs text-slate-400">{camera.source_type.replace(/_/g, " ")}</td>
                <td className="px-4 py-2">
                  <StatusBadge status={camera.connection_status} />
                </td>
                <td className="px-4 py-2 text-xs text-slate-400">
                  {formatCoordinates(camera.location?.latitude, camera.location?.longitude)}
                </td>
                <td className="px-4 py-2 text-xs text-slate-400">{formatDateTime(camera.last_seen_at)}</td>
                <td className="px-4 py-2 text-xs text-slate-300">{camera.is_enabled ? "Yes" : "No"}</td>
                <td className="px-4 py-2 text-right">
                  <div className="flex justify-end gap-2">
                    <a
                      href={`/command/monitoring?camera=${camera.id}`}
                      className="text-xs text-sky-300 hover:underline"
                    >
                      Monitor
                    </a>
                    {has("camera:manage") ? (
                      <button
                        type="button"
                        onClick={() => void toggle(camera)}
                        className="text-xs text-slate-300 hover:underline"
                      >
                        {camera.is_enabled ? "Disable" : "Enable"}
                      </button>
                    ) : null}
                  </div>
                </td>
              </Row>
            ))}
          </DataTable>
        )}
      </Card>
    </>
  );
}
