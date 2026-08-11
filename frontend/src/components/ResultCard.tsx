"use client";

import { useState } from "react";
import Image from "next/image";
import FeatureScores from "@/components/FeatureScores";
import {
  crossesMidnight,
  formatDate,
  formatDuration,
  formatMoney,
  formatTime,
} from "@/lib/format";
import type { FeatureName, Recommendation } from "@/types/api";

function stopsLabel(stops: number): string {
  if (stops === 0) return "Nonstop";
  return `${stops} stop${stops > 1 ? "s" : ""}`;
}

export default function ResultCard({
  rec,
  label,
  consideredFeatures,
}: {
  rec: Recommendation;
  label?: string;
  consideredFeatures?: Set<FeatureName>;
}) {
  const [expanded, setExpanded] = useState(false);
  const offer = rec.scored.offer;
  const first = offer.segments[0];
  const last = offer.segments[offer.segments.length - 1];
  const stops = offer.layovers.length;
  const price = offer.true_price ?? offer.price;
  const hasFees = offer.true_price != null && offer.true_price > offer.price;
  const hasSavings = offer.true_price != null && offer.true_price < offer.price;
  const airlines = Array.from(new Set(offer.segments.map((s) => s.airline)));
  const cabinBaggageKg = offer.baggage_allowance_kg ?? null;
  const studentCheckedBonusKg = offer.student_baggage_bonus_kg ?? null;
  const hasBaggage = cabinBaggageKg != null || studentCheckedBonusKg != null;

  return (
    <article className="group flex flex-col gap-4 rounded-2xl border border-[#e7e4dd] bg-white p-5 shadow-[0_1px_2px_rgba(26,25,23,0.04)] transition-shadow hover:shadow-[0_6px_24px_-8px_rgba(26,25,23,0.14)] sm:p-6">
      <header className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="flex flex-col items-center">
            <span className="font-serif text-2xl leading-none text-[#1a1917]">
              {String(rec.rank).padStart(2, "0")}
            </span>
            <span className="mt-1 text-[9px] font-medium uppercase tracking-[0.12em] text-[#9c978c]">
              {label ?? "Pick"}
            </span>
          </div>
          <span className="h-9 w-px bg-[#e7e4dd]" />
          {offer.airline_logo ? (
            <Image
              src={offer.airline_logo}
              alt=""
              width={28}
              height={28}
              className="h-7 w-7 rounded object-contain"
              unoptimized
            />
          ) : null}
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-[#1a1917]">
              {airlines.join(" · ")}
            </span>
            <span className="text-xs text-[#8a857b]">
              {stopsLabel(stops)} · {formatDuration(offer.total_duration_minutes)}
            </span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xl font-semibold tracking-tight text-[#1a1917]">
            {formatMoney(price, offer.currency)}
          </div>
          {(hasFees || hasSavings) && (
            <div className="text-xs text-[#a8a399] line-through">
              {formatMoney(offer.price, offer.currency)}
            </div>
          )}
          {hasFees && (
            <div className="text-[11px] font-medium text-emerald-600">incl. bag fees</div>
          )}
          {hasSavings && (
            <div className="text-[11px] font-medium text-emerald-600">
              {offer.student_discount_percent
                ? `student −${Math.round(offer.student_discount_percent)}%`
                : "after discounts"}
            </div>
          )}
        </div>
      </header>

      <div className="flex items-center gap-3 rounded-xl border border-[#efece5] bg-[#faf9f6] px-4 py-3 text-sm text-[#423f3a]">
        <div className="text-center">
          <div className="font-semibold tabular-nums">{formatTime(first.departure_time)}</div>
          <div className="text-xs text-[#8a857b]">{first.departure_airport}</div>
        </div>
        <div className="flex flex-1 flex-col items-center">
          <span className="text-[11px] text-[#8a857b]">
            {formatDuration(offer.total_duration_minutes)}
          </span>
          <div className="relative my-1.5 flex w-full items-center">
            <span className="h-1.5 w-1.5 rounded-full bg-[#c9c4b8]" />
            <div className="h-px flex-1 bg-[#d9d4c8]" />
            <svg
              viewBox="0 0 24 24"
              className="h-3.5 w-3.5 shrink-0 -rotate-45 text-[#4f46e5]"
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M21 16v-2l-8-5V3.5A1.5 1.5 0 0 0 11.5 2 1.5 1.5 0 0 0 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5L21 16Z" />
            </svg>
            <div className="h-px flex-1 bg-[#d9d4c8]" />
            <span className="h-1.5 w-1.5 rounded-full bg-[#c9c4b8]" />
          </div>
          <span className="text-[11px] text-[#8a857b]">{stopsLabel(stops)}</span>
        </div>
        <div className="text-center">
          <div className="font-semibold tabular-nums">
            {formatTime(last.arrival_time)}
            {crossesMidnight(first.departure_time, last.arrival_time) && (
              <sup className="ml-0.5 text-[10px] text-rose-500">+1</sup>
            )}
          </div>
          <div className="text-xs text-[#8a857b]">{last.arrival_airport}</div>
        </div>
      </div>

      {rec.narrative && (
        <p className="border-l-2 border-[#4f46e5]/30 pl-3.5 font-serif text-[15px] italic leading-relaxed text-[#423f3a]">
          {rec.narrative}
        </p>
      )}

      {hasBaggage && (
        <p className="text-xs text-[#6b675f]">
          {cabinBaggageKg != null && (
            <>
              Cabin baggage:{" "}
              <span className="font-medium text-[#1a1917]">{cabinBaggageKg}kg</span>
            </>
          )}
          {studentCheckedBonusKg != null
            ? `${cabinBaggageKg != null ? " · " : ""}+${studentCheckedBonusKg}kg checked baggage (student perk)`
            : ""}
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {rec.pros.length > 0 && (
          <ul className="flex flex-col gap-1.5">
            {rec.pros.map((pro, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <svg
                  viewBox="0 0 20 20"
                  className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0L3.3 9.7a1 1 0 1 1 1.4-1.4l3.3 3.3 6.8-6.8a1 1 0 0 1 1.4 0Z"
                    clipRule="evenodd"
                  />
                </svg>
                {pro}
              </li>
            ))}
          </ul>
        )}
        {rec.cons.length > 0 && (
          <ul className="flex flex-col gap-1.5">
            {rec.cons.map((con, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-500">
                <svg
                  viewBox="0 0 20 20"
                  className="mt-0.5 h-4 w-4 shrink-0 text-amber-500"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16Zm0 4a1 1 0 0 1 1 1v3a1 1 0 1 1-2 0V7a1 1 0 0 1 1-1Zm0 8.5a1.1 1.1 0 1 0 0-2.2 1.1 1.1 0 0 0 0 2.2Z"
                    clipRule="evenodd"
                  />
                </svg>
                {con}
              </li>
            ))}
          </ul>
        )}
      </div>

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="inline-flex items-center gap-1 self-start text-xs font-medium text-[#4f46e5] transition-colors hover:text-[#4338ca]"
      >
        <svg
          viewBox="0 0 24 24"
          className={`h-3.5 w-3.5 transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
        {expanded ? "Hide details" : "Show details & scores"}
      </button>

      {expanded && (
        <div className="flex flex-col gap-4 border-t border-[#efece5] pt-4">
          <FeatureScores scored={rec.scored} consideredFeatures={consideredFeatures} />
          <ol className="flex flex-col gap-2">
            {offer.segments.map((seg, i) => (
              <li key={i} className="text-xs text-slate-600">
                <span className="font-medium text-slate-800">
                  {seg.departure_airport} → {seg.arrival_airport}
                </span>{" "}
                · {seg.airline} {seg.flight_number} ·{" "}
                {formatDate(seg.departure_time)} {formatTime(seg.departure_time)}–
                {formatTime(seg.arrival_time)}
                {seg.aircraft ? ` · ${seg.aircraft}` : ""}
                {seg.often_delayed ? " · often delayed" : ""}
                {i < offer.layovers.length && (
                  <div className="pl-3 text-[11px] text-slate-400">
                    Layover at {offer.layovers[i].airport} ·{" "}
                    {formatDuration(offer.layovers[i].duration_minutes)}
                    {offer.layovers[i].overnight ? " · overnight" : ""}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </article>
  );
}
