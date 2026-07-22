import { FEATURE_LABELS } from "@/lib/format";
import type { FeatureName, ScoredFlight } from "@/types/api";

const FEATURE_ORDER: FeatureName[] = [
  "price",
  "duration",
  "stops",
  "layover_quality",
  "arrival_fit",
  "reliability",
  "aircraft_match",
  "carbon",
  "luggage_fit",
];

/**
 * The backend stores *weighted* contributions in `feature_scores`, so we
 * normalize each bar against the max contribution to show relative strengths.
 * Features that were never considered (zero weight everywhere, e.g. carbon when
 * eco-ranking is off) are passed in via `consideredFeatures` and hidden.
 */
export default function FeatureScores({
  scored,
  consideredFeatures,
}: {
  scored: ScoredFlight;
  consideredFeatures?: Set<FeatureName>;
}) {
  const scores = scored.feature_scores;
  const features = consideredFeatures
    ? FEATURE_ORDER.filter((f) => consideredFeatures.has(f))
    : FEATURE_ORDER;
  const max = Math.max(...features.map((f) => scores[f] ?? 0), 0.0001);

  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-2">
      {features.map((feature) => {
        const value = scores[feature] ?? 0;
        const pct = Math.round((value / max) * 100);
        return (
          <div key={feature} className="flex items-center gap-2">
            <span className="w-20 shrink-0 text-[11px] text-slate-500">
              {FEATURE_LABELS[feature]}
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-linear-to-r from-indigo-500 to-violet-400 transition-[width] duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
