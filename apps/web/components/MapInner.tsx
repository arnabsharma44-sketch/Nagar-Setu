"use client";

import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";

export interface MapPoint {
  id: string;
  latitude: number;
  longitude: number;
  label: string;
  detail?: string;
  layer: string;
  href?: string;
}

const LAYER_COLOURS: Record<string, string> = {
  historical_accident: "#dc2626",
  confirmed_observation: "#059669",
  pending_candidate: "#d97706",
  camera: "#0284c7",
  asset: "#7c3aed",
  hotspot: "#be123c",
  event: "#2563eb",
};

export default function MapInner({ points }: { points: MapPoint[] }) {
  const tileUrl =
    process.env.NEXT_PUBLIC_MAP_TILE_URL ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const attribution =
    process.env.NEXT_PUBLIC_MAP_TILE_ATTRIBUTION ?? "&copy; OpenStreetMap contributors";
  const center: [number, number] = points.length
    ? [points[0].latitude, points[0].longitude]
    : [20.2961, 85.8245];

  return (
    <MapContainer center={center} zoom={13} scrollWheelZoom={false} className="h-full w-full">
      <TileLayer url={tileUrl} attribution={attribution} />
      {points.map((point) => (
        <CircleMarker
          key={`${point.layer}-${point.id}`}
          center={[point.latitude, point.longitude]}
          radius={8}
          pathOptions={{
            color: LAYER_COLOURS[point.layer] ?? "#334155",
            fillColor: LAYER_COLOURS[point.layer] ?? "#334155",
            fillOpacity: 0.65,
            weight: 2,
          }}
        >
          <Popup>
            <strong>{point.label}</strong>
            {point.detail ? (
              <span style={{ display: "block", marginTop: 4 }}>{point.detail}</span>
            ) : null}
            <span style={{ display: "block", marginTop: 4, fontSize: 11, color: "#475569" }}>
              {point.layer.replace(/_/g, " ")}
            </span>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
