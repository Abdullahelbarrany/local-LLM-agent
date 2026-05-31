import { useCallback, useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import { OnboardingModal } from "./components/OnboardingModal";
import { Sidebar } from "./components/Sidebar";
import { JobsView } from "./views/JobsView";
import { PipelineView } from "./views/PipelineView";
import { ResumeView } from "./views/ResumeView";

const ONBOARDING_KEY = "onboarding_done";

export function App() {
  const [showOnboarding, setShowOnboarding] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(ONBOARDING_KEY)) {
      setShowOnboarding(true);
    }
  }, []);

  const handleOnboardingComplete = useCallback((keywords: string[], summary: string) => {
    if (keywords.length > 0) {
      localStorage.setItem("cv_keywords", keywords.join(", "));
      localStorage.setItem("cv_summary", summary);
    }
    localStorage.setItem(ONBOARDING_KEY, "1");
    setShowOnboarding(false);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-100">
      {showOnboarding && <OnboardingModal onComplete={handleOnboardingComplete} />}
      <Sidebar />
      <main className="flex-1 overflow-hidden flex flex-col">
        <Routes>
          <Route path="/" element={<JobsView />} />
          <Route path="/resume" element={<ResumeView />} />
          <Route path="/pipeline" element={<PipelineView />} />

        </Routes>
      </main>
    </div>
  );
}
