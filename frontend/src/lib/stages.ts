// Metadata for the LangGraph pipeline nodes, used by the progress timeline.

export interface StageMeta {
  node: string;
  label: string;
  description: string;
}

/** The ordered pipeline stages emitted as `progress` events by the backend. */
export const PIPELINE_STAGES: StageMeta[] = [
  { node: "intake", label: "Understanding your trip", description: "Parsing preferences & picking a persona" },
  { node: "search", label: "Searching flights", description: "Querying Google Flights" },
  { node: "enrich", label: "Adding true costs", description: "Folding in baggage fees" },
  { node: "score", label: "Scoring options", description: "8-criteria trade-off model" },
  { node: "rank", label: "Ranking the best 3", description: "Diverse Pareto-optimal picks" },
  { node: "explain", label: "Writing pros & cons", description: "Plain-English reasoning" },
  { node: "present", label: "Finishing up", description: "Preparing your results" },
];

export const STAGE_ORDER: Record<string, number> = Object.fromEntries(
  PIPELINE_STAGES.map((s, i) => [s.node, i]),
);
