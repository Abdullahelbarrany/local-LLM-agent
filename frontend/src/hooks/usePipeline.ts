import { useCallback, useState } from "react";
import type { Job } from "./useJobSearch";

export interface Pipeline {
  saved: Job[];
  applied: Job[];
  interview: Job[];
  offer: Job[];
}

export function usePipeline() {
  const [pipeline, setPipeline] = useState<Pipeline>({
    saved: [],
    applied: [],
    interview: [],
    offer: [],
  });
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/jobs/pipeline");
      if (!res.ok) throw new Error("Pipeline load failed");
      const data: Pipeline = await res.json();
      setPipeline(data);
    } finally {
      setLoading(false);
    }
  }, []);

  const moveCard = useCallback(
    async (urlHash: string, newStatus: string) => {
      await fetch(`/jobs/${urlHash}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      await load();
    },
    [load]
  );

  const updateNotes = useCallback(async (urlHash: string, notes: string) => {
    await fetch(`/jobs/${urlHash}/notes`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes }),
    });
  }, []);

  return { pipeline, loading, load, moveCard, updateNotes };
}
