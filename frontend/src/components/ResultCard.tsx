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
import type { Recommendation } from "@/types/api";

const RANK_STYLES = [
  "bg-amber-100 text-amber-800 ring-amber-200",
  "bg-slate-100 text-slate-700 ring-slate-200",
  "bg-orange-100 text-orange-800 ring-orange-200",
];

function stopsLabel(stops: number): string {
  if (stops === 0) return "Nonstop";
  return `${stops} stop${stops > 1 ? "s" : ""}`;
}

export default function ResultCard({ rec }: { rec: Recommendation }) {
  const [expanded, setExpanded] = useState(false);
  const offer = rec.scored.offer;
  const first = offer.segments[0];
  const last = offer.segments[offer.segments.length - 1];
  const stops = offer.layovers.length;
  const price = offer.true_price ?? offer.price;
  const hasFees = offer.true_price != null && offer.true_price > offer.price;
  const hasSavings = offer.true_price != null && offer.true_price < offer.price;
  const airlines = Array.from(new Set(offer.segments.map((s) => s.airline)));
  const hasBaggage =
    offer.baggage_allowance_kg != null || offer.student_baggage_bonus_kg != null;
  const totalBagKg =
    (offer.baggage_allowance_kg ?? 0) + (offer.student_baggage_bonus_kg ?? 0);

  return (
    <article className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <header className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span
            className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ring-1 ${
              RANK_STYLES[rec.rank - 1] ?? RANK_STYLES[1]
            }`}
          >
            {rec.rank}
          </span>
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
            <span className="text-sm font-semibold text-slate-900">
              {airlines.join(" · ")}
            </span>
            <span className="text-xs text-slate-400">
              {stopsLabel(stops)} · {formatDuration(offer.total_duration_minutes)}
            </span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold text-slate-900">
            {formatMoney(price, offer.currency)}
          </div>
          {(hasFees || hasSavings) && (
            <div className="text-xs text-slate-400 line-through">
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

      <div className="flex items-center gap-3 text-sm text-slate-700">
        <div className="text-center">
          <div className="font-semibold">{formatTime(first.departure_time)}</div>
          <div className="text-xs text-slate-400">{first.departure_airport}</div>
        </div>
        <div className="flex flex-1 flex-col items-center">
          <span className="text-[11px] text-slate-400">
            {formatDuration(offer.total_duration_minutes)}
          </span>
          <div className="my-1 h-px w-full bg-slate-200" />
          <span className="text-[11px] text-slate-400">{stopsLabel(stops)}</span>
        </div>
        <div className="text-center">
          <div className="font-semibold">
            {formatTime(last.arrival_time)}
            {crossesMidnight(first.departure_time, last.arrival_time) && (
              <sup className="ml-0.5 text-[10px] text-rose-500">+1</sup>
            )}
          </div>
          <div className="text-xs text-slate-400">{last.arrival_airport}</div>
        </div>
      </div>

      {rec.narrative && (
        <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm italic text-slate-600">
          {rec.narrative}
        </p>
      )}

      {hasBaggage && (
        <p className="text-xs text-slate-500">
          Cabin baggage: <span className="font-medium text-slate-700">{totalBagKg}kg</span>
          {offer.student_baggage_bonus_kg
            ? ` (incl. +${offer.student_baggage_bonus_kg}kg student bonus)`
            : ""}
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {rec.pros.length > 0 && (
          <ul className="flex flex-col gap-1">
            {rec.pros.map((pro, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-700">
                <span className="text-emerald-500">✓</span>
                {pro}
              </li>
            ))}
          </ul>
        )}
        {rec.cons.length > 0 && (
          <ul className="flex flex-col gap-1">
            {rec.cons.map((con, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-500">
                <span className="text-amber-500">!</span>
                {con}
              </li>
            ))}
          </ul>
        )}
      </div>

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="self-start text-xs font-medium text-indigo-600 hover:text-indigo-800"
      >
        {expanded ? "Hide details" : "Show details & scores"}
      </button>

      {expanded && (
        <div className="flex flex-col gap-4 border-t border-slate-100 pt-4">
          <FeatureScores scored={rec.scored} />
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
