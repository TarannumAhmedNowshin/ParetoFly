const STEPS: { title: string; body: string }[] = [
  {
    title: "Describe your trip",
    body: "Plain language, no jargon — dates, who's flying, and any preferences.",
  },
  {
    title: "It searches & prices",
    body: "Live fares across airlines, with baggage fees and discounts folded in.",
  },
  {
    title: "It weighs the trade-offs",
    body: "Eight criteria, balanced to the priorities it detects from your request.",
  },
  {
    title: "You get three picks",
    body: "Pareto-optimal and genuinely different, each with clear pros and cons.",
  },
];

const CRITERIA = [
  "Price",
  "Duration",
  "Stops",
  "Layovers",
  "Arrival fit",
  "Reliability",
  "Aircraft",
  "Carbon",
  "Baggage",
];

/** Editorial explainer shown beside the search form. */
export default function InfoPanel() {
  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-2xl border border-[#e7e4dd] bg-white p-6 shadow-[0_1px_2px_rgba(26,25,23,0.04)]">
        <h3 className="font-serif text-lg tracking-tight text-[#1a1917]">
          How it works
        </h3>
        <ol className="mt-4 flex flex-col gap-4">
          {STEPS.map((step, i) => (
            <li key={step.title} className="flex gap-3.5">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-[#e7e4dd] font-serif text-[13px] text-[#1a1917]">
                {i + 1}
              </span>
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-semibold text-[#1a1917]">
                  {step.title}
                </span>
                <span className="text-[13px] leading-relaxed text-[#6b675f]">
                  {step.body}
                </span>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="rounded-2xl border border-[#e7e4dd] bg-white p-6 shadow-[0_1px_2px_rgba(26,25,23,0.04)]">
        <h3 className="font-serif text-lg tracking-tight text-[#1a1917]">
          What the agent weighs
        </h3>
        <p className="mt-1 text-[13px] leading-relaxed text-[#6b675f]">
          Every option is scored across these dimensions, then ranked for balance
          rather than any single number.
        </p>
        <ul className="mt-4 flex flex-wrap gap-2">
          {CRITERIA.map((c) => (
            <li
              key={c}
              className="rounded-lg border border-[#efece5] bg-[#faf9f6] px-2.5 py-1 text-[12.5px] font-medium text-[#423f3a]"
            >
              {c}
            </li>
          ))}
        </ul>
      </section>

      <p className="px-1 text-[12px] leading-relaxed text-[#8a857b]">
        No accounts, no tracking. Your trip details are used only to rank flights
        for this search.
      </p>
    </div>
  );
}
