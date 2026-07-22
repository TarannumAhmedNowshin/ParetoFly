"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { airportLabel, findAirport, searchAirports } from "@/lib/airports";

interface Props {
  label: string;
  value: string; // selected IATA code (e.g. "DAC")
  onChange: (code: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

const inputClass =
  "rounded-xl border border-slate-200 bg-white/90 px-3.5 py-2.5 text-sm text-slate-900 shadow-sm transition-colors focus:border-indigo-400 focus:outline-none focus:ring-4 focus:ring-indigo-500/10 hover:border-slate-300";
const labelClass = "flex flex-col gap-1.5 text-xs font-medium text-slate-500";

/** Autocomplete for airports: type a city/airport/country name, submit an IATA code. */
export default function AirportSelect({ label, value, onChange, placeholder, disabled }: Props) {
  const [query, setQuery] = useState(() => {
    const a = findAirport(value);
    return a ? airportLabel(a) : value;
  });
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  // Keep the text in sync when the code is changed from outside (e.g. swap).
  useEffect(() => {
    const a = findAirport(value);
    setQuery(a ? airportLabel(a) : value);
  }, [value]);

  const results = useMemo(() => searchAirports(query), [query]);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function select(code: string) {
    const a = findAirport(code);
    onChange(code);
    setQuery(a ? airportLabel(a) : code);
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      setOpen(true);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => Math.min(results.length - 1, h + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(0, h - 1));
    } else if (e.key === "Enter") {
      if (open && results[highlight]) {
        e.preventDefault();
        select(results[highlight].code);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className={labelClass} ref={containerRef}>
      {label}
      <div className="relative">
        <input
          className={`${inputClass} w-full`}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setHighlight(0);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          role="combobox"
          aria-expanded={open}
          aria-autocomplete="list"
          autoComplete="off"
        />
        {open && results.length > 0 && (
          <ul className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
            {results.map((a, i) => (
              <li key={a.code}>
                <button
                  type="button"
                  className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm ${
                    i === highlight ? "bg-indigo-50" : "hover:bg-slate-50"
                  }`}
                  onMouseEnter={() => setHighlight(i)}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => select(a.code)}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium text-slate-900">
                      {a.city}, {a.country}
                    </span>
                    <span className="block truncate text-xs text-slate-500">{a.name}</span>
                  </span>
                  <span className="shrink-0 rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                    {a.code}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
