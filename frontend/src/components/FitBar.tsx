interface FitBarProps {
  value: number; // 0–100
}

export function FitBar({ value }: FitBarProps) {
  const pct = Math.max(0, Math.min(100, value));
  const color =
    pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-yellow-400" : "bg-red-400";

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          className={`${color} h-2 rounded-full transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-600 w-8 text-right">{pct}%</span>
    </div>
  );
}
