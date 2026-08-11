/** Placeholder card shown while a search is streaming, before results arrive. */
function SkeletonCard() {
  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-[#e7e4dd] bg-white p-5 shadow-[0_1px_2px_rgba(26,25,23,0.04)] sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="flex flex-col items-center gap-1.5">
            <span className="skeleton h-6 w-6 rounded-md" />
            <span className="skeleton h-2 w-10 rounded" />
          </div>
          <span className="h-9 w-px bg-[#e7e4dd]" />
          <span className="skeleton h-7 w-7 rounded" />
          <div className="flex flex-col gap-1.5">
            <span className="skeleton h-3.5 w-28 rounded" />
            <span className="skeleton h-2.5 w-20 rounded" />
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span className="skeleton h-5 w-16 rounded" />
          <span className="skeleton h-2.5 w-10 rounded" />
        </div>
      </div>

      <div className="flex items-center gap-3 rounded-xl border border-[#efece5] bg-[#faf9f6] px-4 py-3">
        <div className="flex flex-col items-center gap-1.5">
          <span className="skeleton h-3.5 w-10 rounded" />
          <span className="skeleton h-2.5 w-8 rounded" />
        </div>
        <div className="skeleton h-px flex-1" />
        <div className="flex flex-col items-center gap-1.5">
          <span className="skeleton h-3.5 w-10 rounded" />
          <span className="skeleton h-2.5 w-8 rounded" />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <span className="skeleton h-2.5 w-full rounded" />
        <span className="skeleton h-2.5 w-4/5 rounded" />
      </div>
    </div>
  );
}

export default function ResultSkeleton() {
  return (
    <div className="flex flex-col gap-5" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
