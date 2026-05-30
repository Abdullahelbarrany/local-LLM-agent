import { Briefcase, FileText, Kanban, UserCircle } from "lucide-react";
import { NavLink } from "react-router-dom";

const NAV = [
  {
    to: "/",
    icon: Briefcase,
    label: "Jobs",
    hint: "Search & rank job listings",
  },
  {
    to: "/resume",
    icon: FileText,
    label: "Resume",
    hint: "AI resume & cover letter tailoring",
  },
  {
    to: "/pipeline",
    icon: Kanban,
    label: "Pipeline",
    hint: "Track your applications",
  },
];

export function Sidebar() {
  const resetProfile = () => {
    localStorage.removeItem("onboarding_done");
    localStorage.removeItem("cv_keywords");
    localStorage.removeItem("cv_summary");
    window.location.reload();
  };

  return (
    <nav className="w-48 bg-gray-900 flex flex-col py-4 shrink-0">
      {/* Brand */}
      <div className="px-4 pb-4 border-b border-gray-700">
        <p className="text-white font-bold text-sm tracking-tight">Job Workbench</p>
        <p className="text-gray-500 text-xs mt-0.5">Powered by Ollama</p>
      </div>

      {/* Nav items */}
      <div className="flex-1 flex flex-col gap-1 px-2 pt-3">
        {NAV.map(({ to, icon: Icon, label, hint }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            title={hint}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors group ${
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:bg-gray-700 hover:text-white"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={18} className="shrink-0" />
                <div className="min-w-0">
                  <p className={`text-sm font-medium leading-tight ${isActive ? "text-white" : ""}`}>
                    {label}
                  </p>
                  <p className={`text-[10px] leading-tight truncate mt-0.5 ${isActive ? "text-blue-200" : "text-gray-600 group-hover:text-gray-400"}`}>
                    {hint}
                  </p>
                </div>
              </>
            )}
          </NavLink>
        ))}
      </div>

      {/* Profile reset at bottom */}
      <div className="px-2 pt-2 border-t border-gray-700">
        <button
          onClick={resetProfile}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-gray-500 hover:bg-gray-700 hover:text-gray-300 transition-colors w-full"
          title="Re-run profile setup to update your CV / skills"
        >
          <UserCircle size={18} className="shrink-0" />
          <div className="text-left">
            <p className="text-xs font-medium leading-tight">Update Profile</p>
            <p className="text-[10px] text-gray-600 leading-tight mt-0.5">CV &amp; skills setup</p>
          </div>
        </button>
      </div>
    </nav>
  );
}
