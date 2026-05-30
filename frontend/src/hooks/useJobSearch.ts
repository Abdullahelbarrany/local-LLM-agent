import { useCallback, useState } from "react";

export interface Job {
  url_hash?: string;
  url: string;
  title: string;
  company: string;
  location: string;
  date_posted: string;
  description: string;
  source: string;
  quality_score?: number;
  rejection_reason?: string | null;
  flagged_senior?: boolean;
  remote_friendly?: boolean;
  region_open?: boolean;
  fit_score?: number;
  fit_reason?: string;
  matched_keywords?: string[];
  status?: string;
}

const CACHE_KEY = "job_results";

function loadCached(): Job[] {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    return raw ? (JSON.parse(raw) as Job[]) : [];
  } catch {
    return [];
  }
}

function saveCached(jobs: Job[]) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(jobs));
  } catch {
    // storage full — ignore
  }
}

export function useJobSearch() {
  const [results, setResults] = useState<Job[]>(loadCached);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(
    async (query: string, location: string, sources: string[]) => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/jobs/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query, location, sources }),
        });
        if (!res.ok) throw new Error(`Search failed: ${res.status}`);
        const data: Job[] = await res.json();
        setResults(data);
        saveCached(data);
        return data;
      } catch (e) {
        setError(String(e));
        return [];
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const rank = useCallback(async (jobs: Job[], cvKeywords: string[]) => {
    if (!jobs.length) return;
    try {
      const res = await fetch("/jobs/rank", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobs, cv_keywords: cvKeywords }),
      });
      if (!res.ok) throw new Error(`Rank failed: ${res.status}`);
      const ranked: Job[] = await res.json();
      setResults(ranked);
      saveCached(ranked);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const saveJob = useCallback(async (urlHash: string) => {
    await fetch(`/jobs/${urlHash}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "saved" }),
    });
  }, []);

  return { results, loading, error, search, rank, saveJob };
}
