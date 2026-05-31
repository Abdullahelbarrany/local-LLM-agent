import { Briefcase, Search, UserCircle } from "lucide-react";
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { JobCard } from "../components/JobCard";
import type { Job } from "../hooks/useJobSearch";
import { useJobSearch } from "../hooks/useJobSearch";

const SOURCES = [
  "LinkedIn", "Indeed", "Glassdoor", "Wuzzuf", "Bayt",
  "NaukriGulf", "Remotive", "WeWorkRemotely", "Jobicy",
  "Otta", "Himalayas", "Wellfound",
];

const SKELETON_COUNT = 6;

function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-3 animate-pulse">
      <div className="flex gap-2">
        <div className="h-5 w-16 bg-slate-100 rounded-full" />
        <div className="h-5 w-24 bg-slate-50 rounded-full" />
      </div>
      <div className="h-4 w-3/4 bg-slate-100 rounded" />
      <div className="h-3 w-1/2 bg-slate-50 rounded" />
      <div className="h-2 bg-slate-100 rounded-full" />
      <div className="flex gap-1">
        {[1, 2, 3].map((i) => <div key={i} className="h-5 w-12 bg-slate-50 rounded" />)}
      </div>
    </div>
  );
}

export function JobsView() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("Remote");
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [minFit, setMinFit] = useState(0);
  const [hideSenior, setHideSenior] = useState(false);
  const [regionOnly, setRegionOnly] = useState(false);
  const [cvKeywords, setCvKeywords] = useState<string>(
    () => localStorage.getItem("cv_keywords") ?? ""
  );
  const hasProfile = Boolean(localStorage.getItem("cv_keywords"));

  const { results, loading, error, search, rank, saveJob, updateJobStatus } = useJobSearch();

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    const jobs = await search(query, location, selectedSources);
    if (jobs.length) {
      const kws = cvKeywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);
      if (kws.length) await rank(jobs, kws);
    }
  }, [query, location, selectedSources, cvKeywords, search, rank]);

  const toggleSource = (src: string) => {
    setSelectedSources((prev) =>
      prev.includes(src) ? prev.filter((s) => s !== src) : [...prev, src]
    );
  };

  const saveKeywords = (val: string) => {
    setCvKeywords(val);
    localStorage.setItem("cv_keywords", val);
  };

  const filtered = results.filter((j: Job) => {
    if (hideSenior && j.flagged_senior) return false;
    if ((j.fit_score ?? 0) < minFit) return false;
    if (regionOnly && !j.remote_friendly && !j.region_open) return false;
    return true;
  });

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Search header */}
      <div className="bg-white border-b border-slate-200 p-4 space-y-3 shadow-sm">
        <div className="flex gap-2">
          <input
            className="flex-1 bg-slate-50 border border-slate-200 text-slate-800 placeholder:text-slate-400 rounded-xl px-3 py-2 text-sm focus:border-green-500 focus:ring-0 focus:outline-none transition-colors"
            placeholder="Job title, skills, or keywords…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <input
            className="w-40 bg-slate-50 border border-slate-200 text-slate-800 placeholder:text-slate-400 rounded-xl px-3 py-2 text-sm focus:border-green-500 focus:ring-0 focus:outline-none transition-colors"
            placeholder="Remote, Egypt…"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-xl text-sm font-medium disabled:opacity-40 transition-all hover:shadow-md"
          >
            <Search size={15} />
            {loading ? "Searching…" : "Search"}
          </button>
        </div>

        {/* CV Keywords */}
        <div className="flex items-start gap-2">
          <span className="text-xs text-slate-400 shrink-0 mt-2">Your skills:</span>
          <div className="flex-1">
            <input
              className="w-full bg-slate-50 border border-slate-200 text-slate-800 placeholder:text-slate-400 rounded-lg px-2.5 py-1.5 text-xs focus:border-green-500 focus:ring-0 focus:outline-none transition-colors"
              placeholder={hasProfile ? "" : "No skills set — use 'Update Profile' in the sidebar to upload your CV"}
              value={cvKeywords}
              onChange={(e) => saveKeywords(e.target.value)}
            />
            {!hasProfile && (
              <p className="text-[10px] text-amber-600 mt-1">
                ⚠ Jobs will not be ranked without a skill profile. Click <strong>Update Profile</strong> in the sidebar.
              </p>
            )}
          </div>
        </div>

        {/* Source toggle pills */}
        <div className="flex flex-wrap gap-1.5">
          {SOURCES.map((src) => (
            <button
              key={src}
              onClick={() => toggleSource(src)}
              className={`px-2.5 py-1 rounded-lg text-xs transition-all ${
                selectedSources.includes(src)
                  ? "bg-green-100 text-green-700 border border-green-300 font-medium"
                  : "bg-slate-100 text-slate-500 border border-slate-200 hover:text-slate-800 hover:bg-slate-200"
              }`}
            >
              {src}
            </button>
          ))}
        </div>
      </div>

      {/* Filter bar */}
      {results.length > 0 && (
        <div className="bg-slate-50 border-b border-slate-200 px-4 py-2 flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Min fit:</span>
            <input
              type="range"
              min={0}
              max={100}
              value={minFit}
              onChange={(e) => setMinFit(Number(e.target.value))}
              className="w-28 accent-green-600"
            />
            <span className="text-xs text-slate-700 w-8 tabular-nums">{minFit}%</span>
          </div>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={hideSenior}
              onChange={(e) => setHideSenior(e.target.checked)}
              className="rounded accent-green-600"
            />
            <span className="text-xs text-slate-500">Hide senior roles</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={regionOnly}
              onChange={(e) => setRegionOnly(e.target.checked)}
              className="rounded accent-green-600"
            />
            <span className="text-xs text-slate-500">Remote / MENA·EMEA·Africa only</span>
          </label>
          <span className="text-xs text-slate-400 ml-auto tabular-nums">
            {filtered.length} / {results.length} jobs
          </span>
        </div>
      )}

      {/* Results */}
      <div className="flex-1 overflow-y-auto p-4">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl p-3 mb-4">
            {error}
          </div>
        )}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filtered.map((job: Job, i: number) => (
              <JobCard
                key={job.url ?? i}
                job={job}
                onSave={(hash) => saveJob(hash)}
                onStatusChange={updateJobStatus}
              />
            ))}
            {!loading && results.length === 0 && (
              <div className="col-span-full flex flex-col items-center justify-center h-64 gap-4 text-center px-8">
                <Briefcase size={40} className="text-green-300" />
                <div>
                  <p className="font-medium text-slate-400">No jobs yet</p>
                  <p className="text-sm text-slate-400 mt-1">
                    Type a job title or skill above and press Search. Results from 12 job sites will appear here, ranked by how well they match your profile.
                  </p>
                </div>
                {!hasProfile && (
                  <button
                    onClick={() => {
                      localStorage.removeItem("onboarding_done");
                      navigate(0);
                    }}
                    className="flex items-center gap-2 text-sm text-green-600 hover:text-green-700 font-medium transition-colors"
                  >
                    <UserCircle size={16} />
                    Set up your profile first for better rankings
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
