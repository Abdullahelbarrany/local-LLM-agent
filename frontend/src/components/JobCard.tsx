import { AlertTriangle, BookmarkCheck, BookmarkPlus, ExternalLink, Globe, Laptop, Wand2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Job } from "../hooks/useJobSearch";
import { FitBar } from "./FitBar";

const SOURCE_COLORS: Record<string, string> = {
  LinkedIn: "bg-blue-100 text-blue-700",
  Indeed: "bg-indigo-100 text-indigo-700",
  Glassdoor: "bg-green-100 text-green-700",
  Wuzzuf: "bg-orange-100 text-orange-700",
  Bayt: "bg-red-100 text-red-700",
  NaukriGulf: "bg-pink-100 text-pink-700",
  Remotive: "bg-teal-100 text-teal-700",
  WeWorkRemotely: "bg-cyan-100 text-cyan-700",
  Jobicy: "bg-violet-100 text-violet-700",
  Otta: "bg-lime-100 text-lime-700",
  Himalayas: "bg-amber-100 text-amber-700",
  Wellfound: "bg-fuchsia-100 text-fuchsia-700",
};

const STATUS_OPTIONS = [
  { value: "saved",     label: "Saved",     color: "bg-gray-100 text-gray-700" },
  { value: "applied",   label: "Applied",   color: "bg-blue-100 text-blue-700" },
  { value: "interview", label: "Interview", color: "bg-yellow-100 text-yellow-700" },
  { value: "offer",     label: "Offer",     color: "bg-green-100 text-green-700" },
  { value: "rejected",  label: "Rejected",  color: "bg-red-100 text-red-700" },
];

interface JobCardProps {
  job: Job;
  onSave?: (urlHash: string) => Promise<void> | void;
}

export function JobCard({ job, onSave }: JobCardProps) {
  const navigate = useNavigate();
  const hash = job.url_hash ?? btoa(job.url).replace(/[^a-z0-9]/gi, "").slice(0, 16);
  const sourceColor = SOURCE_COLORS[job.source] ?? "bg-gray-100 text-gray-700";

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
  };

  const currentStatusOption = STATUS_OPTIONS.find((s) => s.value === status);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex flex-col gap-3 hover:shadow-md transition-shadow">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${sourceColor}`}>
              {job.source}
            </span>
            {job.flagged_senior && (
              <span className="flex items-center gap-1 text-xs text-yellow-700 bg-yellow-50 px-2 py-0.5 rounded-full border border-yellow-200">
                <AlertTriangle size={11} /> Senior role
              </span>
            )}
            {job.remote_friendly && (
              <span className="flex items-center gap-1 text-xs text-teal-700 bg-teal-50 px-2 py-0.5 rounded-full border border-teal-200">
                <Laptop size={11} /> Remote
              </span>
            )}
            {job.region_open && (
              <span className="flex items-center gap-1 text-xs text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full border border-purple-200">
                <Globe size={11} /> MENA/EMEA/Africa
              </span>
            )}
          </div>
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-semibold text-gray-900 hover:text-blue-600 flex items-center gap-1 leading-snug"
          >
            {job.title}
            <ExternalLink size={12} className="shrink-0 text-gray-400" />
          </a>
          <p className="text-sm text-gray-500 mt-0.5">
            {job.company}
            {job.location ? ` · ${job.location}` : ""}
          </p>
        </div>
      </div>

      {/* Fit score */}
      {job.fit_score !== undefined && (
        <div>
          <p className="text-xs text-gray-400 mb-1">Fit score</p>
          <FitBar value={job.fit_score} />
          {job.fit_reason && (
            <p className="text-xs text-gray-500 mt-1 italic">{job.fit_reason}</p>
          )}
        </div>
      )}

      {/* Matched keywords */}
      {job.matched_keywords && job.matched_keywords.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {job.matched_keywords.slice(0, 8).map((kw) => (
            <span
              key={kw}
              className="text-xs bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded"
            >
              {kw}
            </span>
          ))}
          {job.matched_keywords.length > 8 && (
            <span className="text-xs text-gray-400">+{job.matched_keywords.length - 8}</span>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-1 border-t border-gray-100">
        <span className="text-xs text-gray-400">{job.date_posted || "—"}</span>
        <div className="flex gap-2 items-center">
          {status ? (
            /* Status picker — shown once job is saved */
            <select
              value={status}
              onChange={(e) => handleStatusChange(e.target.value)}
              className={`text-xs px-2 py-1 rounded-lg border-0 font-medium cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-300 ${currentStatusOption?.color ?? "bg-gray-100 text-gray-700"}`}
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          ) : (
            /* Save button — shown before first save */
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 transition-colors disabled:opacity-50"
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
            className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
          >
            <Wand2 size={13} /> Tailor CV
          </button>
        </div>
      </div>
    </div>
  );
}
