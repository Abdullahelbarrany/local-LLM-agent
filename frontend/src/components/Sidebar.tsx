import { Briefcase, FileText, Kanban, Sparkles, UserCircle } from "lucide-react";
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
    <nav className="group relative w-14 hover:w-52 transition-all duration-200 bg-white border-r border-slate-200 flex flex-col py-4 shrink-0 overflow-hidden z-10 shadow-sm">
      {/* Brand */}
      <div className="flex items-center gap-3 px-4 pb-4 border-b border-slate-100 min-w-[208px]">
        <Sparkles size={20} className="text-green-600 shrink-0" />
        <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-150 whitespace-nowrap">
          <p className="text-slate-800 font-semibold text-sm tracking-tight leading-tight">
            Job Workbench
          </p>
          <p className="text-slate-400 text-[10px] mt-0.5">Powered by Ollama</p>
        </div>
      </div>

      {/* Nav items */}
      <div className="flex-1 flex flex-col gap-0.5 px-2 pt-3">
        {NAV.map(({ to, icon: Icon, label, hint }) => (
          <div key={to} className="relative group/item">
            <NavLink
              to={to}
              end={to === "/"}
              title={label}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 min-w-[192px] ${
                  isActive
                    ? "border-l-2 border-green-600 bg-green-50 text-green-700 pl-[10px]"
                    : "border-l-2 border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-50 pl-[10px]"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={18} className="shrink-0" />
                  <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-150 whitespace-nowrap">
                    <p className={`text-sm font-medium leading-tight ${isActive ? "text-green-700" : ""}`}>
                      {label}
                    </p>
                    <p className={`text-[10px] leading-tight mt-0.5 ${isActive ? "text-green-500" : "text-slate-400"}`}>
                      {hint}
                    </p>
                  </div>
                </>
              )}
            </NavLink>
            {/* Tooltip when collapsed */}
            <div className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-white whitespace-nowrap opacity-0 group-hover/item:opacity-100 group-hover:opacity-0 transition-opacity duration-100 shadow-xl z-50">
              {label}
            </div>
          </div>
        ))}
      </div>

      {/* Profile reset */}
      <div className="px-2 pt-2 border-t border-slate-100">
        <div className="relative group/update">
          <button
            onClick={resetProfile}
            title="Update Profile"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg border-l-2 border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-50 transition-all duration-150 w-full min-w-[192px] pl-[10px]"
          >
            <UserCircle size={18} className="shrink-0" />
            <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-150 text-left whitespace-nowrap">
              <p className="text-xs font-medium leading-tight">Update Profile</p>
              <p className="text-[10px] text-slate-400 leading-tight mt-0.5">CV &amp; skills setup</p>
            </div>
          </button>
          <div className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-white whitespace-nowrap opacity-0 group-hover/update:opacity-100 group-hover:opacity-0 transition-opacity duration-100 shadow-xl z-50">
            Update Profile
          </div>
        </div>
      </div>
    </nav>
  );
}
