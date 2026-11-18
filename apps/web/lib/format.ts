/** Presentation helpers shared by Command Center and Admin Portal. */

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "2-digit" });
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes && bytes !== 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function humanise(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatCoordinates(latitude?: number | null, longitude?: number | null): string {
  if (latitude === null || latitude === undefined || longitude === null || longitude === undefined) {
    return "Location unknown";
  }
  return `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
}

const TONE_NEUTRAL = "bg-slate-500/15 text-slate-600 ring-slate-500/30";
const TONE_INFO = "bg-sky-500/15 text-sky-700 ring-sky-500/30";
const TONE_SUCCESS = "bg-emerald-500/15 text-emerald-700 ring-emerald-500/30";
const TONE_WARN = "bg-amber-500/15 text-amber-700 ring-amber-500/30";
const TONE_DANGER = "bg-rose-500/15 text-rose-700 ring-rose-500/30";

const STATUS_TONES: Record<string, string> = {
  pending: TONE_WARN,
  queued: TONE_INFO,
  running: TONE_INFO,
  processing: TONE_INFO,
  succeeded: TONE_SUCCESS,
  processed: TONE_SUCCESS,
  confirmed: TONE_SUCCESS,
  verified: TONE_SUCCESS,
  accepted: TONE_SUCCESS,
  approved: TONE_SUCCESS,
  active: TONE_SUCCESS,
  online: TONE_SUCCESS,
  matched_records: TONE_SUCCESS,
  rejected_false_positive: TONE_DANGER,
  rejected: TONE_DANGER,
  failed: TONE_DANGER,
  validation_failed: TONE_DANGER,
  needs_more_information: TONE_WARN,
  needs_more_evidence: TONE_WARN,
  ambiguous_match: TONE_WARN,
  requires_field_verification: TONE_WARN,
  missing_contract_data: TONE_WARN,
  completed_pending_verification: TONE_WARN,
  simulated: TONE_WARN,
  in_progress: TONE_INFO,
  assigned: TONE_INFO,
  under_review: TONE_INFO,
  reopened: TONE_WARN,
  cancelled: TONE_NEUTRAL,
  draft: TONE_NEUTRAL,
  no_asset_match: TONE_NEUTRAL,
  offline: TONE_NEUTRAL,
  unknown: TONE_NEUTRAL,
  closed: TONE_NEUTRAL,
};

export function statusTone(status: string | null | undefined): string {
  if (!status) return TONE_NEUTRAL;
  return STATUS_TONES[status] ?? TONE_NEUTRAL;
}
