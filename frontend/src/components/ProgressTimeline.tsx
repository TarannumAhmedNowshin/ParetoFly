"use client";

import { PIPELINE_STAGES, STAGE_ORDER } from "@/lib/stages";

interface Props {
  /** The node name of the most recently received progress event. */
  currentNode: string | null;
  /** Whether the pipeline has fully completed. */
  done: boolean;
}

type StageState = "pending" | "active" | "complete";

function stateFor(index: number, currentIndex: number, done: boolean): StageState {
  if (done) return "complete";
  if (index < currentIndex) return "complete";
  if (index === currentIndex) return "active";
  return "pending";
}

function Dot({ state }: { state: StageState }) {
  if (state === "complete") {
    return (
      <span className="relative z-10 flex h-6 w-6 items-center justify-center rounded-full bg-[#1a1917] text-white">
        <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0L3.3 9.7a1 1 0 1 1 1.4-1.4l3.3 3.3 6.8-6.8a1 1 0 0 1 1.4 0Z"
            clipRule="evenodd"
          />
        </svg>
      </span>
    );
  }
  if (state === "active") {
    return (
      <span className="relative z-10 flex h-6 w-6 items-center justify-center rounded-full border-2 border-[#4f46e5] bg-white">
        <span className="h-2.5 w-2.5 animate-ping rounded-full bg-[#4f46e5]" />
        <span className="absolute h-2 w-2 rounded-full bg-[#4f46e5]" />
      </span>
    );
  }
  return (
    <span className="relative z-10 h-6 w-6 rounded-full border-2 border-[#e7e4dd] bg-white" />
  );
}

export default function ProgressTimeline({ currentNode, done }: Props) {
  const currentIndex = currentNode != null ? STAGE_ORDER[currentNode] ?? 0 : 0;

  return (
    <div className="animate-fade-up rounded-2xl border border-[#e7e4dd] bg-white p-6 shadow-[0_1px_2px_rgba(26,25,23,0.04)]">
      <div className="mb-5 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#8a857b]">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#4f46e5]" />
        Working on your search
      </div>
      <ol className="relative flex flex-col gap-5">
        <span
          className="absolute left-3 top-3 bottom-3 w-px -translate-x-1/2 bg-[#e7e4dd]"
          aria-hidden="true"
        />
        {PIPELINE_STAGES.map((stage, i) => {
          const state = stateFor(i, currentIndex, done);
          return (
            <li key={stage.node} className="relative flex items-start gap-3.5">
              <Dot state={state} />
              <div className="flex flex-col pt-0.5">
                <span
                  className={
                    state === "pending"
                      ? "text-sm font-medium text-[#a8a399]"
                      : "text-sm font-semibold text-[#1a1917]"
                  }
                >
                  {stage.label}
                </span>
                <span className="text-xs text-[#8a857b]">{stage.description}</span>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
