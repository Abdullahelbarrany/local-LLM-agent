import { useEffect, useState } from "react";

interface FitBarProps {
  value: number; // 0–100
}

export function FitBar({ value }: FitBarProps) {
  const pct = Math.max(0, Math.min(100, value));
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const gradient =
    pct >= 70
      ? "bg-gradient-to-r from-green-500 to-emerald-400"
      : pct >= 40
      ? "bg-gradient-to-r from-amber-400 to-yellow-400"
      : "bg-gradient-to-r from-red-500 to-red-400";

  const scoreColor =
    pct >= 70
      ? "text-green-600"
      : pct >= 40
      ? "text-amber-500"
      : "text-red-500";

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
        <div
          className={`${gradient} h-2 rounded-full transition-all duration-700 ease-out`}
          style={{ width: mounted ? `${pct}%` : "0%" }}
        />
      </div>
      <span className={`text-sm font-semibold w-9 text-right tabular-nums ${scoreColor}`}>
        {pct}%
      </span>
    </div>
  );
}
