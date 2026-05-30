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
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm space-y-3 animate-pulse">
      <div className="flex gap-2">
        <div className="h-5 w-16 bg-gray-200 rounded-full" />
        <div className="h-5 w-24 bg-gray-100 rounded-full" />
      </div>
      <div className="h-4 w-3/4 bg-gray-200 rounded" />
      <div className="h-3 w-1/2 bg-gray-100 rounded" />
      <div className="h-2 bg-gray-200 rounded-full" />
      <div className="flex gap-1">
        {[1, 2, 3].map((i) => <div key={i} className="h-5 w-12 bg-gray-100 rounded" />)}
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

  const { results, loading, error, search, rank, saveJob } = useJobSearch();

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
      {/* Search bar */}
      <div className="bg-white border-b border-gray-200 p-4 space-y-3">
        <div className="flex gap-2">
          <input
            className="flex-1 border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
            placeholder="Job title, skills, or keywords…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <input
            className="w-40 border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
            placeholder="Remote, Egypt…"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm disabled:opacity-40 transition-colors"
          >
            <Search size={15} />
            {loading ? "Searching…" : "Search"}
          </button>
        </div>

        {/* CV Keywords — shown as editable chip list */}
        <div className="flex items-start gap-2">
          <span className="text-xs text-gray-500 shrink-0 mt-1.5">Your skills:</span>
          <div className="flex-1">
            <input
              className="w-full border border-gray-200 rounded-lg px-2.5 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-200"
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

        {/* Source checkboxes */}
        <div className="flex flex-wrap gap-1.5">
          {SOURCES.map((src) => (
            <label key={src} className="flex items-center gap-1 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedSources.includes(src)}
                onChange={() => toggleSource(src)}
                className="rounded text-blue-600"
              />
              <span className="text-xs text-gray-600">{src}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Filter bar */}
      {results.length > 0 && (
        <div className="bg-gray-50 border-b border-gray-200 px-4 py-2 flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Min fit:</span>
            <input
              type="range"
              min={0}
              max={100}
              value={minFit}
              onChange={(e) => setMinFit(Number(e.target.value))}
              className="w-28"
            />
            <span className="text-xs text-gray-700 w-8">{minFit}%</span>
          </div>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={hideSenior}
              onChange={(e) => setHideSenior(e.target.checked)}
              className="rounded text-blue-600"
            />
            <span className="text-xs text-gray-600">Hide senior roles</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={regionOnly}
              onChange={(e) => setRegionOnly(e.target.checked)}
              className="rounded text-blue-600"
            />
            <span className="text-xs text-gray-600">Remote / MENA·EMEA·Africa only</span>
          </label>
          <span className="text-xs text-gray-400 ml-auto">
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
              />
            ))}
            {!loading && results.length === 0 && (
              <div className="col-span-full flex flex-col items-center justify-center h-64 gap-4 text-center px-8">
                <Briefcase size={40} className="text-gray-300" />
                <div>
                  <p className="font-medium text-gray-600">No jobs yet</p>
                  <p className="text-sm text-gray-400 mt-1">
                    Type a job title or skill above and press Search. Results from 12 job sites will appear here, ranked by how well they match your profile.
                  </p>
                </div>
                {!hasProfile && (
                  <button
                    onClick={() => {
                      localStorage.removeItem("onboarding_done");
                      navigate(0);
                    }}
                    className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 font-medium"
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
