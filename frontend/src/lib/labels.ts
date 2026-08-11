import type { FeatureName, Recommendation } from "@/types/api";

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

const FEATURE_PICK_LABEL: Record<FeatureName, string> = {
  price: "Best value",
  duration: "Fastest",
  stops: "Fewest stops",
  layover_quality: "Smoothest layovers",
  arrival_fit: "Best arrival time",
  reliability: "Most reliable",
  aircraft_match: "Most comfortable",
  carbon: "Greenest",
  luggage_fit: "Best for baggage",
};

/**
 * Label each recommendation by the criterion where it stands out most against
 * the others. We rank (feature, leading pick) pairs by the margin over the
 * runner-up, then greedily assign so every pick gets a distinct label.
 */
export function derivePickLabels(recs: Recommendation[]): Record<string, string> {
  const labels: Record<string, string> = {};
  if (recs.length === 0) return labels;

  type Candidate = {
    feature: FeatureName;
    recId: string;
    margin: number;
    lead: number;
  };
  const candidates: Candidate[] = [];

  for (const feature of FEATURE_ORDER) {
    const values = recs.map((r) => ({
      id: r.scored.offer.id,
      v: r.scored.feature_scores[feature] ?? 0,
    }));
    const sorted = [...values].sort((a, b) => b.v - a.v);
    const top = sorted[0];
    if (!top || top.v <= 0) continue; // feature carried no weight
    const runnerUp = sorted[1]?.v ?? 0;
    candidates.push({
      feature,
      recId: top.id,
      margin: top.v - runnerUp,
      lead: top.v,
    });
  }

  candidates.sort((a, b) => b.margin - a.margin || b.lead - a.lead);

  const usedRecs = new Set<string>();
  const usedFeatures = new Set<FeatureName>();
  for (const c of candidates) {
    if (usedRecs.has(c.recId) || usedFeatures.has(c.feature)) continue;
    labels[c.recId] = FEATURE_PICK_LABEL[c.feature];
    usedRecs.add(c.recId);
    usedFeatures.add(c.feature);
    if (usedRecs.size === recs.length) break;
  }

  for (const r of recs) {
    if (!labels[r.scored.offer.id]) {
      labels[r.scored.offer.id] = r.rank === 1 ? "Best overall" : "Balanced pick";
    }
  }

  return labels;
}
