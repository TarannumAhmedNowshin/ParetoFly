"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CURRENCIES, findCurrency, flagUrl, searchCurrencies } from "@/lib/currencies";

interface Props {
  label?: string;
  value: string; // ISO 4217 code, e.g. "USD"
  onChange: (code: string) => void;
  disabled?: boolean;
}

const labelClass = "flex flex-col gap-1.5 text-xs font-medium text-slate-500";
const controlClass =
  "flex w-full items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white/90 px-3.5 py-2.5 text-sm text-slate-900 shadow-sm transition-colors focus:border-indigo-400 focus:outline-none focus:ring-4 focus:ring-indigo-500/10 hover:border-slate-300 disabled:opacity-50";

function Flag({ cc, className }: { cc: string; className?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- tiny external flag asset
    <img
      src={flagUrl(cc)}
      srcSet={`${flagUrl(cc, 2)} 2x`}
      width={20}
      height={15}
      alt=""
      loading="lazy"
      className={`h-3.75 w-5 shrink-0 rounded-xs object-cover ring-1 ring-black/5 ${className ?? ""}`}
    />
  );
}

/** Searchable currency picker with country flags. */
export default function CurrencySelect({ label = "Currency", value, onChange, disabled }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = findCurrency(value) ?? CURRENCIES[0];
  const results = useMemo(() => searchCurrencies(query), [query]);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setHighlight(0);
      // Focus the search field when the dropdown opens.
      const id = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(id);
    }
  }, [open]);

  function select(code: string) {
    onChange(code);
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => Math.min(results.length - 1, h + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(0, h - 1));
    } else if (e.key === "Enter") {
      if (results[highlight]) {
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
        <button
          type="button"
          className={controlClass}
          onClick={() => !disabled && setOpen((o) => !o)}
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <span className="flex min-w-0 items-center gap-2">
            <Flag cc={selected.flag} />
            <span className="font-semibold text-slate-900">{selected.code}</span>
            <span className="truncate text-xs text-slate-400">{selected.name}</span>
          </span>
          <svg
            className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </button>

        {open && (
          <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
            <div className="border-b border-slate-100 p-2">
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setHighlight(0);
                }}
                onKeyDown={onKeyDown}
                placeholder="Search currency or code…"
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:border-indigo-400 focus:outline-none focus:ring-4 focus:ring-indigo-500/10"
                aria-label="Search currencies"
                autoComplete="off"
              />
            </div>
            <ul className="max-h-64 overflow-auto py-1" role="listbox">
              {results.length === 0 && (
                <li className="px-3 py-2 text-sm text-slate-400">No matches</li>
              )}
              {results.map((c, i) => {
                const active = c.code === selected.code;
                return (
                  <li key={c.code} role="option" aria-selected={active}>
                    <button
                      type="button"
                      className={`flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm ${
                        i === highlight ? "bg-indigo-50" : "hover:bg-slate-50"
                      }`}
                      onMouseEnter={() => setHighlight(i)}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => select(c.code)}
                    >
                      <Flag cc={c.flag} />
                      <span className="w-10 shrink-0 font-semibold text-slate-900">{c.code}</span>
                      <span className="min-w-0 flex-1 truncate text-slate-600">{c.name}</span>
                      {active && (
                        <svg
                          viewBox="0 0 20 20"
                          className="h-4 w-4 shrink-0 text-indigo-600"
                          fill="currentColor"
                          aria-hidden="true"
                        >
                          <path
                            fillRule="evenodd"
                            d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0L3.3 9.7a1 1 0 1 1 1.4-1.4l3.3 3.3 6.8-6.8a1 1 0 0 1 1.4 0Z"
                            clipRule="evenodd"
                          />
                        </svg>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
