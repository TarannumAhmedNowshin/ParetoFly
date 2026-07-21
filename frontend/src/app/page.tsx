"use client";

import { useCallback, useRef, useState } from "react";
import SearchForm from "@/components/SearchForm";
import ProgressTimeline from "@/components/ProgressTimeline";
import ResultCard from "@/components/ResultCard";
import { searchStream } from "@/lib/api";
import type { SearchResult, TripQuery } from "@/types/api";

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

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-4 py-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          Pareto<span className="text-indigo-600">Fly</span>
        </h1>
        <p className="text-sm text-slate-500">
          Tell us your trip and priorities — we&apos;ll return the top&nbsp;3
          Pareto-optimal flights with plain-English pros&nbsp;&amp;&nbsp;cons.
        </p>
      </header>

      <SearchForm onSearch={handleSearch} disabled={streaming} />

      {streaming && <ProgressTimeline currentNode={currentNode} done={false} />}

      {phase === "error" && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
          <p className="font-semibold">We couldn&apos;t complete your search.</p>
          <p className="mt-1">{errorMsg}</p>
        </div>
      )}

      {phase === "done" && recommendations.length === 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
          No flights matched this search. Try widening your dates, stops, or budget.
        </div>
      )}

      {recommendations.length > 0 && (
        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold text-slate-900">Your top 3</h2>
          {recommendations.map((rec) => (
            <ResultCard key={rec.scored.offer.id} rec={rec} />
          ))}
        </section>
      )}
    </main>
  );
}
