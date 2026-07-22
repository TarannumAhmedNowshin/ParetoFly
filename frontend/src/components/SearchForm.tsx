"use client";

import { useState } from "react";
import type { CabinClass, Persona, TripQuery } from "@/types/api";
import AirportSelect from "@/components/AirportSelect";
import DatePicker from "@/components/DatePicker";
import { findAirport } from "@/lib/airports";

const CABIN_OPTIONS: { value: CabinClass; label: string }[] = [
  { value: "economy", label: "Economy" },
  { value: "premium_economy", label: "Premium economy" },
  { value: "business", label: "Business" },
  { value: "first", label: "First" },
];

const PERSONA_OPTIONS: { value: Persona | ""; label: string }[] = [
  { value: "", label: "Auto-detect" },
  { value: "student", label: "Student (budget-first)" },
  { value: "business", label: "Business (time-first)" },
  { value: "family", label: "Family (comfort-first)" },
];

interface Props {
  onSearch: (query: TripQuery) => void;
  disabled?: boolean;
}

function Stepper({
  label,
  value,
  min,
  onChange,
  disabled,
}: {
  label: string;
  value: number;
  min: number;
  onChange: (v: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-slate-500">{label}</span>
      <div className="flex items-center rounded-lg border border-slate-300 bg-white">
        <button
          type="button"
          className="px-3 py-2 text-slate-500 hover:text-slate-900 disabled:opacity-40"
          onClick={() => onChange(Math.max(min, value - 1))}
          disabled={disabled || value <= min}
          aria-label={`Decrease ${label}`}
        >
          –
        </button>
        <span className="min-w-8 text-center text-sm font-semibold text-slate-900">{value}</span>
        <button
          type="button"
          className="px-3 py-2 text-slate-500 hover:text-slate-900 disabled:opacity-40"
          onClick={() => onChange(value + 1)}
          disabled={disabled}
          aria-label={`Increase ${label}`}
        >
          +
        </button>
      </div>
    </div>
  );
}

const inputClass =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200";
const labelClass = "flex flex-col gap-1 text-xs font-medium text-slate-500";

export default function SearchForm({ onSearch, disabled }: Props) {
  const [tripType, setTripType] = useState<"round_trip" | "one_way">("round_trip");
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [departDate, setDepartDate] = useState("");
  const [returnDate, setReturnDate] = useState("");
  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState(0);
  const [infants, setInfants] = useState(0);
  const [cabin, setCabin] = useState<CabinClass>("economy");
  const [currency, setCurrency] = useState("USD");
  const [freeText, setFreeText] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [budget, setBudget] = useState("");
  const [maxStops, setMaxStops] = useState("");
  const [maxLayover, setMaxLayover] = useState("");
  const [persona, setPersona] = useState<Persona | "">("");
  const [isStudent, setIsStudent] = useState(false);
  const [carryOnOnly, setCarryOnOnly] = useState(false);
  const [ecoFriendly, setEcoFriendly] = useState(false);
  const [arriveStart, setArriveStart] = useState("");
  const [arriveEnd, setArriveEnd] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!findAirport(origin) || !findAirport(destination)) {
      setError("Please pick an origin and destination from the suggestions.");
      return;
    }
    if (origin === destination) {
      setError("Origin and destination must be different.");
      return;
    }
    if (!departDate) {
      setError("Please choose a departure date.");
      return;
    }
    if (tripType === "round_trip" && !returnDate) {
      setError("Please choose a return date, or switch to one-way.");
      return;
    }
    if (returnDate && returnDate < departDate) {
      setError("Return date cannot be before departure.");
      return;
    }

    const hourFrom = (v: string): number | null =>
      v ? Number(v.split(":")[0]) : null;
    const arrStart = hourFrom(arriveStart);
    const arrEnd = hourFrom(arriveEnd);
    const freeTextParts: string[] = [];
    if (freeText.trim()) freeTextParts.push(freeText.trim());
    if (carryOnOnly) freeTextParts.push("carry-on only");
    if (arrStart !== null && arrEnd !== null) {
      freeTextParts.push(`arrive between ${arriveStart} and ${arriveEnd}`);
    }

    const query: TripQuery = {
      origin,
      destination,
      depart_date: departDate,
      return_date: tripType === "round_trip" ? returnDate || null : null,
      adults,
      children,
      infants,
      cabin,
      currency: currency.trim().toUpperCase() || "USD",
      free_text: freeTextParts.join(". ") || null,
      budget: budget ? Number(budget) : null,
      max_stops: maxStops === "" ? null : Number(maxStops),
      max_layover_minutes: maxLayover === "" ? null : Number(maxLayover),
      is_student: isStudent,
      eco_friendly: ecoFriendly,
      persona: persona || null,
    };
    onSearch(query);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-5 rounded-2xl border border-slate-200 bg-white/80 p-6 shadow-sm backdrop-blur"
    >
      <div
        role="radiogroup"
        aria-label="Trip type"
        className="inline-flex self-start rounded-lg border border-slate-300 bg-slate-100 p-0.5"
      >
        {([
          { value: "round_trip", label: "Round trip" },
          { value: "one_way", label: "One way" },
        ] as const).map((opt) => (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={tripType === opt.value}
            onClick={() => setTripType(opt.value)}
            disabled={disabled}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors disabled:opacity-40 ${
              tripType === opt.value
                ? "bg-white text-indigo-600 shadow-sm"
                : "text-slate-500 hover:text-slate-900"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white px-4 py-3">
        <div className="flex flex-col">
          <span className="flex items-center gap-2 text-sm font-medium text-slate-900">
            <svg
              className={`h-4 w-4 ${ecoFriendly ? "text-emerald-600" : "text-slate-400"}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
              <path d="M2 21c0-3 1.85-5.36 5.08-6" />
            </svg>
            Eco-friendly flight
          </span>
          <span className="mt-0.5 text-xs text-slate-400">
            {ecoFriendly
              ? "Lower-emission flights are favored in ranking."
              : "Carbon emissions are ignored unless enabled."}
          </span>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={ecoFriendly}
          aria-label="Eco-friendly flight"
          onClick={() => setEcoFriendly((v) => !v)}
          disabled={disabled}
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-40 ${
            ecoFriendly ? "bg-emerald-500" : "bg-slate-300"
          }`}
        >
          <span
            className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
              ecoFriendly ? "translate-x-5" : "translate-x-0.5"
            }`}
          />
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <AirportSelect
          label="From"
          value={origin}
          onChange={setOrigin}
          placeholder="City or airport, e.g. Dhaka"
          disabled={disabled}
        />
        <AirportSelect
          label="To"
          value={destination}
          onChange={setDestination}
          placeholder="City or airport, e.g. Los Angeles"
          disabled={disabled}
        />
        <DatePicker
          label="Departure"
          value={departDate}
          onChange={setDepartDate}
          disabled={disabled}
          className={tripType === "one_way" ? "sm:col-span-2" : ""}
        />
        {tripType === "round_trip" && (
          <DatePicker
            label="Return"
            value={returnDate}
            onChange={setReturnDate}
            min={departDate || undefined}
            disabled={disabled}
          />
        )}
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Stepper label="Adults" value={adults} min={1} onChange={setAdults} disabled={disabled} />
        <Stepper label="Children" value={children} min={0} onChange={setChildren} disabled={disabled} />
        <Stepper label="Infants" value={infants} min={0} onChange={setInfants} disabled={disabled} />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label className={labelClass}>
          Cabin
          <select
            className={inputClass}
            value={cabin}
            onChange={(e) => setCabin(e.target.value as CabinClass)}
            disabled={disabled}
          >
            {CABIN_OPTIONS.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        <label className={labelClass}>
          Currency
          <input
            className={inputClass}
            value={currency}
            onChange={(e) => setCurrency(e.target.value.toUpperCase().slice(0, 3))}
            maxLength={3}
            disabled={disabled}
          />
        </label>
      </div>

      <label className={labelClass}>
        Tell us about your trip
        <textarea
          className={`${inputClass} min-h-24 resize-y`}
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
          placeholder="e.g. afternoon arrival, no red-eyes, traveling with a 5-year-old, 2 checked bags"
          disabled={disabled}
        />
      </label>

      <button
        type="button"
        className="self-start text-sm font-medium text-indigo-600 hover:text-indigo-800"
        onClick={() => setShowAdvanced((v) => !v)}
      >
        {showAdvanced ? "− Hide" : "+ Refine"} advanced options
      </button>

      {showAdvanced && (
        <div className="grid grid-cols-1 gap-4 rounded-xl bg-slate-50 p-4 sm:grid-cols-3">
          <label className={labelClass}>
            Max budget
            <input
              type="number"
              min={1}
              className={inputClass}
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="e.g. 500"
              disabled={disabled}
            />
          </label>
          <label className={labelClass}>
            Max stops
            <select
              className={inputClass}
              value={maxStops}
              onChange={(e) => setMaxStops(e.target.value)}
              disabled={disabled}
            >
              <option value="">Any</option>
              <option value="0">Nonstop</option>
              <option value="1">1 stop</option>
              <option value="2">2 stops</option>
            </select>
          </label>
          <label className={labelClass}>
            Persona
            <select
              className={inputClass}
              value={persona}
              onChange={(e) => setPersona(e.target.value as Persona | "")}
              disabled={disabled}
            >
              {PERSONA_OPTIONS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <label className={labelClass}>
            Max layover
            <select
              className={inputClass}
              value={maxLayover}
              onChange={(e) => setMaxLayover(e.target.value)}
              disabled={disabled}
            >
              <option value="">Any</option>
              <option value="60">1 hour</option>
              <option value="120">2 hours</option>
              <option value="240">4 hours</option>
              <option value="480">8 hours</option>
            </select>
          </label>
          <label className={labelClass}>
            Arrive after
            <input
              type="time"
              className={inputClass}
              value={arriveStart}
              onChange={(e) => setArriveStart(e.target.value)}
              disabled={disabled}
            />
          </label>
          <label className={labelClass}>
            Arrive before
            <input
              type="time"
              className={inputClass}
              value={arriveEnd}
              onChange={(e) => setArriveEnd(e.target.value)}
              disabled={disabled}
            />
          </label>
          <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300"
              checked={isStudent}
              onChange={(e) => setIsStudent(e.target.checked)}
              disabled={disabled}
            />
            I&apos;m a student
          </label>
          <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300"
              checked={carryOnOnly}
              onChange={(e) => setCarryOnOnly(e.target.checked)}
              disabled={disabled}
            />
            Carry-on only
          </label>
        </div>
      )}

      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}

      <button
        type="submit"
        className="rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={disabled}
      >
        {disabled ? "Searching…" : "Find the best 3 flights"}
      </button>
    </form>
  );
}
