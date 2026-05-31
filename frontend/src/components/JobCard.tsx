import { AlertTriangle, BookmarkCheck, BookmarkPlus, ExternalLink, Globe, Laptop, Wand2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Job } from "../hooks/useJobSearch";
import { FitBar } from "./FitBar";

const SOURCE_COLORS: Record<string, string> = {
  LinkedIn:       "bg-blue-100 text-blue-700 border border-blue-200",
  Indeed:         "bg-violet-100 text-violet-700 border border-violet-200",
  Glassdoor:      "bg-green-100 text-green-700 border border-green-200",
  Wuzzuf:         "bg-orange-100 text-orange-700 border border-orange-200",
  Bayt:           "bg-red-100 text-red-700 border border-red-200",
  NaukriGulf:     "bg-pink-100 text-pink-700 border border-pink-200",
  Remotive:       "bg-teal-100 text-teal-700 border border-teal-200",
  WeWorkRemotely: "bg-cyan-100 text-cyan-700 border border-cyan-200",
  Jobicy:         "bg-purple-100 text-purple-700 border border-purple-200",
  Otta:           "bg-lime-100 text-lime-700 border border-lime-200",
  Himalayas:      "bg-amber-100 text-amber-700 border border-amber-200",
  Wellfound:      "bg-fuchsia-100 text-fuchsia-700 border border-fuchsia-200",
};

const STATUS_OPTIONS = [
  { value: "saved",     label: "Saved" },
  { value: "applied",   label: "Applied" },
  { value: "interview", label: "Interview" },
  { value: "offer",     label: "Offer" },
  { value: "rejected",  label: "Rejected" },
];

interface JobCardProps {
  job: Job;
  onSave?: (urlHash: string) => Promise<void> | void;
  onStatusChange?: (urlHash: string, newStatus: string) => void;
}

export function JobCard({ job, onSave, onStatusChange }: JobCardProps) {
  const navigate = useNavigate();
  const hash = job.url_hash ?? btoa(job.url).replace(/[^a-z0-9]/gi, "").slice(0, 16);
  const sourceColor = SOURCE_COLORS[job.source] ?? "bg-slate-100 text-slate-600 border border-slate-200";

  const [status, setStatus] = useState<string | null>(job.status ?? null);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave?.(hash);
      setStatus("saved");
    } finally {
      setSaving(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    setStatus(newStatus);
    await fetch(`/jobs/${hash}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    });
    onStatusChange?.(hash, newStatus);
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-4 flex flex-col gap-3 hover:border-green-400 hover:shadow-md transition-all duration-200">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap mb-2">
            <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${sourceColor}`}>
              {job.source}
            </span>
            {job.flagged_senior && (
              <span className="flex items-center gap-1 text-[10px] text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full border border-amber-200">
                <AlertTriangle size={10} /> Senior
              </span>
            )}
            {job.remote_friendly && (
              <span className="flex items-center gap-1 text-[10px] text-teal-700 bg-teal-100 px-2 py-0.5 rounded-full border border-teal-200">
                <Laptop size={10} /> Remote
              </span>
            )}
            {job.region_open && (
              <span className="flex items-center gap-1 text-[10px] text-purple-700 bg-purple-100 px-2 py-0.5 rounded-full border border-purple-200">
                <Globe size={10} /> MENA/EMEA
              </span>
            )}
          </div>
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-semibold text-[15px] text-slate-800 hover:text-green-700 flex items-center gap-1.5 leading-snug transition-colors"
          >
            {job.title}
            <ExternalLink size={12} className="shrink-0 text-slate-400" />
          </a>
          <p className="text-sm text-slate-500 mt-0.5">
            {job.company}
            {job.location ? ` · ${job.location}` : ""}
          </p>
        </div>
      </div>

      {/* Fit score */}
      {job.fit_score !== undefined && (
        <div>
          <p className="text-[10px] text-slate-400 uppercase tracking-widest mb-1.5">Fit</p>
          <FitBar value={job.fit_score} />
          {job.fit_reason && (
            <p className="text-xs text-slate-500 mt-1.5 italic leading-relaxed">{job.fit_reason}</p>
          )}
        </div>
      )}

      {/* Matched keywords */}
      {job.matched_keywords && job.matched_keywords.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {job.matched_keywords.slice(0, 8).map((kw) => (
            <span
              key={kw}
              className="text-xs bg-green-50 text-green-700 border border-green-200 px-1.5 py-0.5 rounded"
            >
              {kw}
            </span>
          ))}
          {job.matched_keywords.length > 8 && (
            <span className="text-xs text-slate-400">+{job.matched_keywords.length - 8}</span>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-100">
        <span className="text-xs text-slate-400">{job.date_posted || "—"}</span>
        <div className="flex gap-2 items-center">
          {status ? (
            <select
              value={status}
              onChange={(e) => handleStatusChange(e.target.value)}
              className="text-xs px-2 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-700 font-medium cursor-pointer focus:outline-none focus:ring-2 focus:ring-green-400/40 transition-colors"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          ) : (
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-800 transition-all disabled:opacity-50"
            >
              {saving ? (
                <BookmarkCheck size={13} className="animate-pulse" />
              ) : (
                <BookmarkPlus size={13} />
              )}
              {saving ? "Saving…" : "Save"}
            </button>
          )}
          <button
            onClick={() => {
              localStorage.setItem(`job_ctx_${hash}`, JSON.stringify(job));
              navigate(`/resume?job=${encodeURIComponent(hash)}&title=${encodeURIComponent(job.title)}&company=${encodeURIComponent(job.company)}`);
            }}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-xl bg-green-600 hover:bg-green-500 text-white font-medium transition-all hover:shadow-md"
          >
            <Wand2 size={13} /> Tailor CV
          </button>
        </div>
      </div>
    </div>
  );
}
