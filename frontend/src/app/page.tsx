"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import SearchForm from "@/components/SearchForm";
import ProgressTimeline from "@/components/ProgressTimeline";
import ResultCard from "@/components/ResultCard";
import { searchStream, reportUrl } from "@/lib/api";
import type { FeatureName, SearchResult, TripQuery } from "@/types/api";

type Phase = "idle" | "streaming" | "done" | "error";

export default function Home() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleSearch = useCallback(async (query: TripQuery) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setPhase("streaming");
    setCurrentNode(null);
    setResult(null);
    setErrorMsg(null);

    try {
      await searchStream(query, {
        signal: controller.signal,
        onProgress: (evt) => setCurrentNode(evt.node),
        onResult: (res) => {
          setResult(res);
          setPhase(res.error ? "error" : "done");
          if (res.error) setErrorMsg(res.error);
        },
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      setErrorMsg(err instanceof Error ? err.message : "Something went wrong.");
      setPhase("error");
    }
  }, []);

  const streaming = phase === "streaming";
  const recommendations = result?.recommendations ?? [];

  // A feature is only "considered" if it contributed to the score of at least
  // one recommendation. Features with zero weight (e.g. carbon when eco-ranking
  // is off) contribute nothing everywhere, so we hide them from the breakdown.
  const consideredFeatures = useMemo(() => {
    const set = new Set<FeatureName>();
    for (const rec of recommendations) {
      for (const [feature, value] of Object.entries(rec.scored.feature_scores)) {
        if (value > 0) set.add(feature as FeatureName);
      }
    }
    return set;
  }, [recommendations]);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-4 py-10 sm:py-14">
      <header className="flex flex-col gap-3 animate-fade-up">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 shadow-sm">
            <svg
              viewBox="0 0 24 24"
              className="h-5 w-5 text-white"
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M21 16v-2l-8-5V3.5A1.5 1.5 0 0 0 11.5 2 1.5 1.5 0 0 0 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5L21 16Z" />
            </svg>
          </span>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Pareto<span className="text-indigo-600">Fly</span>
          </h1>
        </div>

        <p className="max-w-xl text-[15px] leading-relaxed text-slate-500">
          Describe your trip the way you&apos;d tell a friend. Like a tireless
          travel agent, our AI reads between the lines&nbsp;— weighing price,
          time, comfort and reliability across every option&nbsp;— and hands you
          the{" "}
          <span className="font-medium text-slate-700">3 smartest flights</span>,
          each with plain-English pros&nbsp;&amp;&nbsp;cons.
        </p>
      </header>

      <div className="animate-fade-up" style={{ animationDelay: "80ms" }}>
        <SearchForm onSearch={handleSearch} disabled={streaming} />
      </div>

      {streaming && <ProgressTimeline currentNode={currentNode} done={false} />}

      {phase === "error" && (
        <div className="animate-fade-up rounded-2xl border border-rose-200 bg-rose-50/80 p-6 text-sm text-rose-700 shadow-sm backdrop-blur">
          <p className="font-semibold">We couldn&apos;t complete your search.</p>
          <p className="mt-1">{errorMsg}</p>
        </div>
      )}

      {phase === "done" && recommendations.length === 0 && (
        <div className="animate-fade-up rounded-2xl border border-slate-200 bg-white/80 p-6 text-sm text-slate-600 shadow-sm backdrop-blur">
          No flights matched this search. Try widening your dates, stops, or budget.
        </div>
      )}

      {recommendations.length > 0 && (
        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">
              Your top 3
            </h2>
            {result?.session_id && (
              <a
                href={reportUrl(result.session_id)}
                download
                className="group inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-white/70 px-3 py-1.5 text-sm font-medium text-indigo-700 shadow-sm backdrop-blur transition hover:border-indigo-300 hover:bg-indigo-50"
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-4 w-4 transition-transform group-hover:translate-y-0.5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M12 3v12m0 0 4-4m-4 4-4-4" />
                  <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
                </svg>
                Download report
              </a>
            )}
          </div>
          {recommendations.map((rec, i) => (
            <div
              key={rec.scored.offer.id}
              className="animate-fade-up"
              style={{ animationDelay: `${i * 90}ms` }}
            >
              <ResultCard rec={rec} consideredFeatures={consideredFeatures} />
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
