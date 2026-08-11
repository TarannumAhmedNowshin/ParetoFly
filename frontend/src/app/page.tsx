"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import SearchForm from "@/components/SearchForm";
import ProgressTimeline from "@/components/ProgressTimeline";
import ResultCard from "@/components/ResultCard";
import InfoPanel from "@/components/InfoPanel";
import { searchStream, reportUrl } from "@/lib/api";
import { derivePickLabels } from "@/lib/labels";
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

  const pickLabels = useMemo(
    () => derivePickLabels(recommendations),
    [recommendations],
  );

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col px-5 sm:px-6">
      <header className="flex items-center justify-between gap-4 border-b border-[#e7e4dd] py-5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#1a1917] text-[#fafaf8]">
            <svg
              viewBox="0 0 24 24"
              className="h-4.5 w-4.5"
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M21 16v-2l-8-5V3.5A1.5 1.5 0 0 0 11.5 2 1.5 1.5 0 0 0 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5L21 16Z" />
            </svg>
          </span>
          <span className="font-serif text-[22px] leading-none tracking-tight text-[#1a1917]">
            ParetoFly
          </span>
        </div>
        <span className="hidden text-[13px] text-[#6b675f] sm:inline">
          Pareto-optimal flight search
        </span>
      </header>

      <main className="flex flex-col gap-10 pb-16 pt-10 sm:pt-14">
        <section className="grid animate-fade-up items-center gap-8 lg:grid-cols-[1.5fr_1fr]">
          <div className="flex flex-col gap-5">
            <h1 className="font-serif text-4xl leading-[1.08] tracking-tight text-[#1a1917] sm:text-[2.85rem]">
              The three smartest flights for your trip,
              <span className="italic text-[#4f46e5]"> explained</span>.
            </h1>
            <p className="max-w-xl text-[15px] leading-relaxed text-[#6b675f]">
              Describe your journey the way you&apos;d tell a friend. Our agent reads
              between the lines&nbsp;— weighing price, time, comfort and reliability
              across every option&nbsp;— then returns three balanced picks, each with
              clear pros and cons.
            </p>
          </div>

          <div className="relative hidden lg:block" aria-hidden="true">
            <svg viewBox="0 0 420 240" className="w-full">
              <line
                x1="24"
                y1="208"
                x2="396"
                y2="208"
                stroke="#e2ded5"
                strokeWidth="1"
                strokeDasharray="2 7"
              />
              <path
                d="M64 194 Q212 36 360 104"
                fill="none"
                stroke="#c9c4b8"
                strokeWidth="1.5"
                strokeDasharray="5 7"
              />
              <circle cx="64" cy="194" r="11" fill="none" stroke="#dcd7cc" />
              <circle cx="64" cy="194" r="5" fill="#1a1917" />
              <circle cx="360" cy="104" r="22" fill="none" stroke="#e6e3fb" />
              <circle cx="360" cy="104" r="13" fill="none" stroke="#c8c4f4" />
              <circle cx="360" cy="104" r="5" fill="#4f46e5" />
              <g transform="translate(196 56) rotate(26)">
                <path
                  transform="scale(1.5)"
                  fill="#1a1917"
                  d="M21 16v-2l-8-5V3.5A1.5 1.5 0 0 0 11.5 2 1.5 1.5 0 0 0 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5L21 16Z"
                />
              </g>
            </svg>
          </div>
        </section>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)] lg:items-start">
          <div className="animate-fade-up" style={{ animationDelay: "80ms" }}>
            <SearchForm onSearch={handleSearch} disabled={streaming} />
          </div>

          <aside
            className="animate-fade-up lg:sticky lg:top-6"
            style={{ animationDelay: "140ms" }}
          >
            {streaming ? (
              <ProgressTimeline currentNode={currentNode} done={false} />
            ) : (
              <InfoPanel />
            )}
          </aside>
        </div>

        {phase === "error" && (
          <div className="animate-fade-up rounded-2xl border border-rose-200 bg-rose-50/70 p-6 text-sm text-rose-800">
            <p className="font-semibold">We couldn&apos;t complete your search.</p>
            <p className="mt-1 text-rose-700">{errorMsg}</p>
          </div>
        )}

        {streaming && (
          <section className="flex w-full max-w-3xl flex-col gap-5">
            <div className="flex flex-col gap-1 border-b border-[#e7e4dd] pb-4">
              <h2 className="font-serif text-2xl tracking-tight text-[#1a1917]">
                Finding your top three
              </h2>
              <p className="text-[13px] text-[#6b675f]">
                Comparing every option across your priorities…
              </p>
            </div>
            <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-[#e7e4dd] bg-white py-16 shadow-[0_1px_2px_rgba(26,25,23,0.04)]">
              <svg
                className="h-8 w-8 animate-spin text-[#4f46e5]"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
              >
                <circle
                  className="opacity-20"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="3"
                />
                <path
                  className="opacity-90"
                  fill="currentColor"
                  d="M4 12a8 8 0 0 1 8-8V1C5.9 1 1 5.9 1 12h3Z"
                />
              </svg>
              <p className="text-[13px] text-[#8a857b]">Scoring the best options…</p>
            </div>
          </section>
        )}

        {phase === "done" && recommendations.length === 0 && (
          <div className="animate-fade-up rounded-2xl border border-[#e7e4dd] bg-white p-6 text-sm text-[#6b675f] shadow-[0_1px_2px_rgba(26,25,23,0.04)]">
            No flights matched this search. Try widening your dates, stops, or budget.
          </div>
        )}

        {recommendations.length > 0 && (
          <section className="flex w-full max-w-3xl flex-col gap-5">
            <div className="flex items-end justify-between gap-4 border-b border-[#e7e4dd] pb-4">
              <div className="flex flex-col gap-1">
                <h2 className="font-serif text-2xl tracking-tight text-[#1a1917]">
                  Your top three
                </h2>
                <p className="text-[13px] text-[#6b675f]">
                  Ranked for the best balance across your priorities.
                </p>
              </div>
              {result?.session_id && (
                <a
                  href={reportUrl(result.session_id)}
                  download
                  className="group inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-[#e7e4dd] bg-white px-3 py-1.5 text-[13px] font-medium text-[#423f3a] shadow-[0_1px_2px_rgba(26,25,23,0.04)] transition-colors hover:border-[#d6d2c8] hover:bg-[#fafaf8]"
                >
                  <svg
                    viewBox="0 0 24 24"
                    className="h-4 w-4 transition-transform group-hover:translate-y-0.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
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
                <ResultCard
                  rec={rec}
                  label={pickLabels[rec.scored.offer.id]}
                  consideredFeatures={consideredFeatures}
                />
              </div>
            ))}
          </section>
        )}
      </main>

      <footer className="flex items-center justify-between gap-4 border-t border-[#e7e4dd] py-7 text-[13px] text-[#8a857b]">
        <span className="font-serif text-[15px] text-[#423f3a]">ParetoFly</span>
        <span>Balanced flight recommendations, explained.</span>
      </footer>
    </div>
  );
}
