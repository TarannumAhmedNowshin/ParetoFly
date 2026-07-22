"use client";

import { useEffect, useMemo, useRef, useState } from "react";

interface Props {
  label: string;
  value: string; // ISO date "YYYY-MM-DD" or ""
  onChange: (value: string) => void;
  min?: string; // earliest selectable ISO date
  placeholder?: string;
  disabled?: boolean;
  className?: string; // extra classes for the wrapper (e.g. column span)
}

const inputClass =
  "flex items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white/90 px-3.5 py-2.5 text-sm text-slate-900 shadow-sm transition-colors focus:border-indigo-400 focus:outline-none focus:ring-4 focus:ring-indigo-500/10 hover:border-slate-300 disabled:opacity-50";
const labelClass = "flex flex-col gap-1.5 text-xs font-medium text-slate-500";

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function parseISO(s: string): Date | null {
  if (!s) return null;
  const [y, m, d] = s.split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

function toISO(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

/** Date input with a popup month calendar (keyboard + outside-click aware). */
export default function DatePicker({
  label,
  value,
  onChange,
  min,
  placeholder = "Select a date",
  disabled,
  className,
}: Props) {
  const selected = useMemo(() => parseISO(value), [value]);
  const minDate = useMemo(() => parseISO(min ?? ""), [min]);
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<Date>(() => selected ?? minDate ?? new Date());
  const containerRef = useRef<HTMLDivElement>(null);

  // Keep the visible month in sync when the value changes from outside.
  useEffect(() => {
    if (selected) setView(new Date(selected.getFullYear(), selected.getMonth(), 1));
  }, [selected]);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const year = view.getFullYear();
  const month = view.getMonth();
  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date();

  const cells: (Date | null)[] = [];
  for (let i = 0; i < firstWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));

  function isDisabledDay(d: Date): boolean {
    if (!minDate) return false;
    const day = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const floor = new Date(minDate.getFullYear(), minDate.getMonth(), minDate.getDate());
    return day < floor;
  }

  function pick(d: Date) {
    if (isDisabledDay(d)) return;
    onChange(toISO(d));
    setOpen(false);
  }

  const displayText = selected
    ? selected.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
    : placeholder;

  return (
    <div className={`${labelClass} ${className ?? ""}`} ref={containerRef}>
      {label}
      <div className="relative">
        <button
          type="button"
          className={`${inputClass} w-full`}
          onClick={() => !disabled && setOpen((o) => !o)}
          onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
          disabled={disabled}
          aria-haspopup="dialog"
          aria-expanded={open}
        >
          <span className={selected ? "text-slate-900" : "text-slate-400"}>{displayText}</span>
          <svg
            className="h-4 w-4 shrink-0 text-slate-400"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="3" y="4" width="18" height="18" rx="2" />
            <path d="M16 2v4M8 2v4M3 10h18" />
          </svg>
        </button>

        {open && (
          <div
            role="dialog"
            aria-label={`${label} calendar`}
            className="absolute z-30 mt-1 w-72 rounded-xl border border-slate-200 bg-white p-3 shadow-lg"
          >
            <div className="mb-2 flex items-center justify-between">
              <button
                type="button"
                className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                onClick={() => setView(new Date(year, month - 1, 1))}
                aria-label="Previous month"
              >
                ‹
              </button>
              <span className="text-sm font-semibold text-slate-900">
                {MONTHS[month]} {year}
              </span>
              <button
                type="button"
                className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                onClick={() => setView(new Date(year, month + 1, 1))}
                aria-label="Next month"
              >
                ›
              </button>
            </div>

            <div className="mb-1 grid grid-cols-7 text-center text-xs font-medium text-slate-400">
              {WEEKDAYS.map((w) => (
                <span key={w} className="py-1">
                  {w}
                </span>
              ))}
            </div>

            <div className="grid grid-cols-7 gap-0.5">
              {cells.map((d, i) => {
                if (!d) return <span key={`e${i}`} />;
                const isSelected = selected ? sameDay(d, selected) : false;
                const isToday = sameDay(d, today);
                const off = isDisabledDay(d);
                return (
                  <button
                    key={toISO(d)}
                    type="button"
                    onClick={() => pick(d)}
                    disabled={off}
                    className={`h-9 rounded-md text-sm transition-colors ${
                      isSelected
                        ? "bg-indigo-600 font-semibold text-white"
                        : off
                        ? "cursor-not-allowed text-slate-300"
                        : "text-slate-700 hover:bg-indigo-50"
                    } ${!isSelected && isToday ? "ring-1 ring-inset ring-indigo-300" : ""}`}
                  >
                    {d.getDate()}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
