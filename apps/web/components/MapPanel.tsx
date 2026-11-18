"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import type { MapPoint } from "@/components/MapInner";
import { Card, CardHeader, LoadingRows, type Tone } from "@/components/ui";

const MapInner = dynamic(() => import("@/components/MapInner"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-sm text-slate-500">Loading map…</div>
  ),
});

const LEGEND: Array<[string, string]> = [
  ["historical_accident", "Historical accident record"],
  ["confirmed_observation", "Human-confirmed observation"],
  ["pending_candidate", "Pending AI candidate"],
  ["camera", "Registered camera"],
  ["asset", "Infrastructure asset"],
  ["hotspot", "Event concentration"],
];

export function MapPanel({
  tone,
  points,
  title = "Map",
  description = "Coordinates come from registered records only. Unknown locations are never plotted.",
  height = 420,
  loading = false,
}: {
  tone: Tone;
  points: MapPoint[];
  title?: string;
  description?: string;
  height?: number;
  loading?: boolean;
}) {
  return (
    <Card tone={tone}>
      <CardHeader title={title} description={description} tone={tone} />
      <div style={{ height }} className="overflow-hidden rounded-b-xl">
        {loading ? (
          <LoadingRows tone={tone} label="Loading map…" />
        ) : points.length ? (
          <MapInner points={points} />
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-500">
            No located records to plot. Records without coordinates stay in the list view.
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-[#dfe6ee] px-4 py-2 text-xs dark:border-[#1e2b3c]">
        {LEGEND.map(([key, label]) => (
          <span key={key} className="flex items-center gap-1.5 text-slate-500">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: colourFor(key) }}
            />
            {label}
          </span>
        ))}
      </div>
      <div className="border-t border-[#dfe6ee] px-4 py-3 dark:border-[#1e2b3c]">
        <p className="text-xs text-slate-500">
          Map data © OpenStreetMap contributors. A cluster is a record concentration, not an
          exposure-normalised risk rate.{" "}
          <Link className="underline" href="/command/hotspots">
            See hotspot methodology
          </Link>
          .
        </p>
        <ul className="mt-2 space-y-1 text-xs text-slate-500">
          {points.slice(0, 12).map((point) => (
            <li key={`${point.layer}-${point.id}-list`}>
              <span className="font-medium text-slate-700 dark:text-slate-300">{point.label}</span>{" "}
              — {point.detail ?? point.layer.replace(/_/g, " ")} (
              {point.latitude.toFixed(4)}, {point.longitude.toFixed(4)})
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}

function colourFor(layer: string): string {
  switch (layer) {
    case "historical_accident":
      return "#dc2626";
    case "confirmed_observation":
      return "#059669";
    case "pending_candidate":
      return "#d97706";
    case "camera":
      return "#0284c7";
    case "asset":
      return "#7c3aed";
    default:
      return "#be123c";
  }
}
