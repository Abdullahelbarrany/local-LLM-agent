import { AlertCircle, CheckCircle2, ChevronRight, Loader2, Upload, X } from "lucide-react";
import { useRef, useState } from "react";

interface OnboardingModalProps {
  onComplete: (keywords: string[], summary: string) => void;
}

type Step = "upload" | "extracting" | "review";

export function OnboardingModal({ onComplete }: OnboardingModalProps) {
  const [step, setStep] = useState<Step>("upload");
  const [cvText, setCvText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [summary, setSummary] = useState("");
  const [error, setError] = useState("");
  const [removedKws, setRemovedKws] = useState<Set<string>>(new Set());
  const [customKw, setCustomKw] = useState("");
  const [extraKws, setExtraKws] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    if (f && f.type !== "application/pdf") {
      // Read plain text files immediately for preview
      const reader = new FileReader();
      reader.onload = (ev) => setCvText(ev.target?.result as string ?? "");
      reader.readAsText(f);
    }
  };

  const extract = async () => {
    setError("");
    setStep("extracting");

    try {
      const body = new FormData();
      if (file) {
        body.append("file", file);
      } else if (cvText.trim()) {
        body.append("text", cvText);
      } else {
        setError("Please upload a file or paste your CV text.");
        setStep("upload");
        return;
      }

      const res = await fetch("/resume/extract-keywords", { method: "POST", body });
      const text = await res.text();
      if (!text.trim()) {
        throw new Error("Server returned an empty response. The model may have timed out — try again.");
      }
      const data = JSON.parse(text);

      if (!res.ok || data.error) {
        throw new Error(data.error ?? "Extraction failed");
      }

      setKeywords(data.keywords ?? []);
      setSummary(data.summary ?? "");
      setStep("review");
    } catch (e) {
      setError(String(e));
      setStep("upload");
    }
  };

  const toggleKw = (kw: string) => {
    setRemovedKws((prev) => {
      const next = new Set(prev);
      if (next.has(kw)) next.delete(kw);
      else next.add(kw);
      return next;
    });
  };

  const addCustomKw = () => {
    const kw = customKw.trim();
    if (kw && !keywords.includes(kw) && !extraKws.includes(kw)) {
      setExtraKws((prev) => [...prev, kw]);
    }
    setCustomKw("");
  };

  const finalKeywords = [
    ...keywords.filter((k) => !removedKws.has(k)),
    ...extraKws,
  ];

  const finish = () => onComplete(finalKeywords, summary);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Set up your profile</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Upload your CV so the app knows your skills when ranking jobs
              </p>
            </div>
            {step === "review" && (
              <button onClick={finish} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            )}
          </div>

          {/* Step indicator */}
          <div className="flex items-center gap-2 mt-4">
            {(["upload", "extracting", "review"] as Step[]).map((s, i) => (
              <div key={s} className="flex items-center gap-2">
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold transition-colors ${
                    step === s
                      ? "bg-blue-600 text-white"
                      : (["upload", "extracting", "review"].indexOf(step) > i)
                      ? "bg-green-500 text-white"
                      : "bg-gray-200 text-gray-500"
                  }`}
                >
                  {(["upload", "extracting", "review"].indexOf(step) > i) ? (
                    <CheckCircle2 size={14} />
                  ) : i + 1}
                </div>
                <span className={`text-xs ${step === s ? "text-gray-800 font-medium" : "text-gray-400"}`}>
                  {s === "upload" ? "Upload CV" : s === "extracting" ? "Analysing" : "Review skills"}
                </span>
                {i < 2 && <ChevronRight size={14} className="text-gray-300" />}
              </div>
            ))}
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">

          {/* Step 1: Upload */}
          {step === "upload" && (
            <div className="space-y-4">
              {/* File drop zone */}
              <div
                onClick={() => fileRef.current?.click()}
                className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors"
              >
                <Upload size={28} className="mx-auto text-gray-400 mb-2" />
                <p className="text-sm font-medium text-gray-700">
                  {file ? file.name : "Click to upload your CV"}
                </p>
                <p className="text-xs text-gray-400 mt-1">PDF or plain text (.txt)</p>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.txt,.tex"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </div>

              <div className="flex items-center gap-3 text-gray-400 text-xs">
                <div className="flex-1 border-t border-gray-200" />
                or paste below
                <div className="flex-1 border-t border-gray-200" />
              </div>

              <textarea
                className="w-full border border-gray-200 rounded-xl p-3 text-sm text-gray-700 resize-none focus:outline-none focus:ring-2 focus:ring-blue-300 h-36"
                placeholder="Paste your CV / resume text here…"
                value={cvText}
                onChange={(e) => setCvText(e.target.value)}
              />

              {error && (
                <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 rounded-lg p-3">
                  <AlertCircle size={16} className="shrink-0" />
                  {error}
                </div>
              )}
            </div>
          )}

          {/* Step 2: Extracting */}
          {step === "extracting" && (
            <div className="flex flex-col items-center justify-center py-12 gap-4">
              <Loader2 size={40} className="text-blue-600 animate-spin" />
              <p className="text-gray-700 font-medium">Analysing your CV…</p>
              <p className="text-sm text-gray-400 text-center">
                Ollama is reading your experience and extracting your top skills.
                This takes 10–30 seconds.
              </p>
            </div>
          )}

          {/* Step 3: Review */}
          {step === "review" && (
            <div className="space-y-4">
              {summary && (
                <div className="bg-blue-50 rounded-xl p-3 text-sm text-blue-800 border border-blue-100">
                  <span className="font-medium">Profile: </span>{summary}
                </div>
              )}

              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">
                  Extracted skills — click to remove, add your own below:
                </p>
                <div className="flex flex-wrap gap-2 min-h-[60px]">
                  {keywords.map((kw) => (
                    <button
                      key={kw}
                      onClick={() => toggleKw(kw)}
                      className={`px-3 py-1 rounded-full text-sm border transition-colors ${
                        removedKws.has(kw)
                          ? "bg-gray-100 text-gray-400 border-gray-200 line-through"
                          : "bg-blue-100 text-blue-800 border-blue-200 hover:bg-red-50 hover:text-red-600 hover:border-red-200"
                      }`}
                    >
                      {kw}
                    </button>
                  ))}
                  {extraKws.map((kw) => (
                    <button
                      key={kw}
                      onClick={() => setExtraKws((p) => p.filter((k) => k !== kw))}
                      className="px-3 py-1 rounded-full text-sm border bg-green-100 text-green-800 border-green-200 hover:bg-red-50 hover:text-red-600 hover:border-red-200"
                    >
                      {kw}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex gap-2">
                <input
                  className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                  placeholder="Add a skill…"
                  value={customKw}
                  onChange={(e) => setCustomKw(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addCustomKw()}
                />
                <button
                  onClick={addCustomKw}
                  className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm transition-colors"
                >
                  Add
                </button>
              </div>

              <p className="text-xs text-gray-400">
                {finalKeywords.length} skills selected — these will be used to rank jobs for you.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 pb-6 pt-4 border-t border-gray-100 flex justify-between items-center">
          {step === "upload" && (
            <>
              <button
                onClick={finish}
                className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
              >
                Skip for now
              </button>
              <button
                onClick={extract}
                disabled={!file && !cvText.trim()}
                className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-medium disabled:opacity-40 transition-colors"
              >
                Extract my skills
                <ChevronRight size={16} />
              </button>
            </>
          )}

          {step === "review" && (
            <>
              <button
                onClick={() => setStep("upload")}
                className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                ← Re-upload
              </button>
              <button
                onClick={finish}
                disabled={finalKeywords.length === 0}
                className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-medium disabled:opacity-40 transition-colors"
              >
                <CheckCircle2 size={16} />
                Save & start searching
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
