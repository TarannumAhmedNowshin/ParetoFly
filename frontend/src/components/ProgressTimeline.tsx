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
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white">
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
      <span className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-indigo-500">
        <span className="h-2.5 w-2.5 animate-ping rounded-full bg-indigo-500" />
      </span>
    );
  }
  return <span className="h-6 w-6 rounded-full border-2 border-slate-200" />;
}

export default function ProgressTimeline({ currentNode, done }: Props) {
  const currentIndex = currentNode != null ? STAGE_ORDER[currentNode] ?? 0 : 0;

  return (
    <ol className="flex animate-fade-up flex-col gap-4 rounded-3xl border border-white/60 bg-white/70 p-6 shadow-xl shadow-slate-900/5 ring-1 ring-slate-900/5 backdrop-blur-xl">
      {PIPELINE_STAGES.map((stage, i) => {
        const state = stateFor(i, currentIndex, done);
        return (
          <li key={stage.node} className="flex items-start gap-3">
            <Dot state={state} />
            <div className="flex flex-col">
              <span
                className={
                  state === "pending"
                    ? "text-sm font-medium text-slate-400"
                    : "text-sm font-semibold text-slate-900"
                }
              >
                {stage.label}
              </span>
              <span className="text-xs text-slate-400">{stage.description}</span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
