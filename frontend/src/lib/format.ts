import type { FeatureName } from "@/types/api";

/** Format a minute count as "12h 15m". */
export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

/** Format an ISO datetime (no tz) as a local-looking "14:15" time. */
export function formatTime(iso: string): string {
  // Backend datetimes are airport-local without tz info; render the raw HH:MM.
  const t = iso.includes("T") ? iso.split("T")[1] : iso.split(" ")[1] ?? "";
  return t.slice(0, 5);
}

/** Format an ISO datetime as "Aug 15". */
export function formatDate(iso: string): string {
  const datePart = iso.split("T")[0] ?? iso.split(" ")[0] ?? iso;
  const d = new Date(`${datePart}T00:00:00`);
  if (Number.isNaN(d.getTime())) return datePart;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Whether two ISO datetimes fall on different calendar dates. */
export function crossesMidnight(startIso: string, endIso: string): boolean {
  const a = (startIso.split("T")[0] ?? startIso.split(" ")[0]) || "";
  const b = (endIso.split("T")[0] ?? endIso.split(" ")[0]) || "";
  return a !== b;
}

export function formatMoney(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency} ${Math.round(amount)}`;
  }
}

export const FEATURE_LABELS: Record<FeatureName, string> = {
  price: "Price",
  duration: "Duration",
  stops: "Stops",
  layover_quality: "Layovers",
  arrival_fit: "Arrival fit",
  reliability: "Reliability",
  aircraft_match: "Aircraft",
  carbon: "Carbon",
  luggage_fit: "Baggage",
};
