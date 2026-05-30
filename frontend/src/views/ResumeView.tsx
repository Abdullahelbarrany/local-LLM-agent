import { Bot, ChevronRight, Send, Wrench } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useSearchParams } from "react-router-dom";
import type { Job } from "../hooks/useJobSearch";
import { useWebSocket } from "../hooks/useWebSocket";

interface ChatMessage {
  role: "user" | "assistant" | "status";
  content: string;
}

function StatusBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-1.5 text-xs text-gray-400 italic px-2 py-1">
        <Wrench size={11} className="shrink-0" />
        {text}
      </div>
    </div>
  );
}

export function ResumeView() {
  const [searchParams] = useSearchParams();
  const jobParam    = searchParams.get("job");
  const titleParam  = searchParams.get("title");
  const companyParam = searchParams.get("company");

  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [statusLines, setStatusLines] = useState<string[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [jobList, setJobList] = useState<Job[]>([]);
  const [awaitingSelection, setAwaitingSelection] = useState(false);
  const { send, events, connected } = useWebSocket("/resume/chat");
  const bottomRef = useRef<HTMLDivElement>(null);
  const didAutoSend = useRef(false);

  // Stop streaming if the WebSocket drops mid-response
  useEffect(() => {
    if (!connected && streaming) {
      setStreaming(false);
      setStatusLines([]);
      setMessages((prev) => [
        ...prev,
        { role: "status", content: "Connection lost — please try again." },
      ]);
    }
  }, [connected, streaming]);

  // Auto-send when navigated from a job card
  useEffect(() => {
    if (jobParam && titleParam && companyParam && connected && !didAutoSend.current) {
      didAutoSend.current = true;

      // Try to retrieve full job context stored by JobCard
      let jobCtx: Job | null = null;
      try {
        const raw = localStorage.getItem(`job_ctx_${jobParam}`);
        if (raw) jobCtx = JSON.parse(raw) as Job;
      } catch { /* ignore */ }

      let msg = `Please tailor my CV for this role: ${titleParam} at ${companyParam}.`;
      if (jobCtx?.url) {
        msg += `\nJob URL: ${jobCtx.url}`;
      }
      if (jobCtx?.description) {
        msg += `\nJob description (first 600 chars):\n${jobCtx.description.slice(0, 600)}`;
      }

      setMessages([{ role: "user", content: `Tailor CV for: ${titleParam} at ${companyParam}` }]);
      setStreaming(true);
      send({ messages: [{ role: "user", content: msg }] });
    }
  }, [connected, jobParam, titleParam, companyParam, send]);

  useEffect(() => {
    if (!events.length) return;
    const last = events[events.length - 1];

    if (last.type === "token") {
      setStatusLines([]);
      setMessages((prev) => {
        const copy = [...prev];
        const tail = copy[copy.length - 1];
        if (tail?.role === "assistant") {
          copy[copy.length - 1] = { ...tail, content: tail.content + (last.content as string) };
        } else {
          copy.push({ role: "assistant", content: last.content as string });
        }
        return copy;
      });
    } else if (last.type === "done") {
      setStreaming(false);
      setStatusLines([]);
    } else if (last.type === "error") {
      setStreaming(false);
      setStatusLines([]);
      setMessages((prev) => [
        ...prev,
        { role: "status", content: `Error: ${last.message as string}` },
      ]);
    } else if (last.type === "tool_start") {
      setStatusLines((prev) => [...prev, `Calling tool: ${last.tool as string}…`]);
    } else if (last.type === "tool_end") {
      setStatusLines((prev) => prev.filter((l) => !l.startsWith(`Calling tool: ${last.tool as string}`)));
    } else if (last.type === "agent_start") {
      setStatusLines((prev) => [...prev, `Running ${last.agent as string} agent…`]);
    } else if (last.type === "agent_end") {
      setStatusLines((prev) => prev.filter((l) => !l.startsWith(`Running ${last.agent as string}`)));
    } else if (last.type === "job_list") {
      setJobList(last.jobs as Job[]);
    } else if (last.type === "awaiting_selection") {
      setAwaitingSelection(true);
    }
  }, [events]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, statusLines]);

  const submit = (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || streaming || !connected) return;
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setStreaming(true);
    setAwaitingSelection(false);
    send({ messages: [{ role: "user", content: msg }] });
    setInput("");
  };

  const selectJob = (job: Job) => {
    submit(`I want to tailor my CV for: ${job.title} at ${job.company} — ${job.url}`);
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {jobParam && (
        <div className="bg-blue-50 border-b border-blue-200 px-4 py-2 text-sm text-blue-700 flex items-center gap-2">
          <Bot size={14} />
          Tailoring for: <strong>{titleParam}</strong> at <strong>{companyParam}</strong>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && !jobParam && (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm text-center px-8">
            Ask me to tailor your CV, search for jobs, or write a cover letter.
          </div>
        )}

        {messages.map((m, i) => (
          m.role === "status" ? (
            <div key={i} className="flex justify-center">
              <span className="text-xs text-gray-400 italic">{m.content}</span>
            </div>
          ) : (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-2xl px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  m.role === "user"
                    ? "bg-blue-600 text-white rounded-br-sm whitespace-pre-wrap"
                    : "bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm prose prose-sm max-w-none"
                }`}
              >
                {m.role === "assistant" ? (
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                ) : (
                  m.content
                )}
              </div>
            </div>
          )
        ))}

        {/* Live tool/agent status lines */}
        {streaming && statusLines.map((line, i) => (
          <StatusBubble key={i} text={line} />
        ))}

        {/* Selectable job list from search_jobs_multi */}
        {awaitingSelection && jobList.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-xl p-3 shadow-sm space-y-2">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Select a job to tailor your CV for:
            </p>
            {jobList.map((job, i) => (
              <button
                key={i}
                onClick={() => selectJob(job)}
                className="w-full text-left px-3 py-2 rounded-lg hover:bg-blue-50 border border-gray-100 transition-colors flex items-center justify-between"
              >
                <div>
                  <p className="font-medium text-sm text-gray-900">{job.title}</p>
                  <p className="text-xs text-gray-500">{job.company} · {job.location}</p>
                </div>
                <ChevronRight size={14} className="text-gray-400 shrink-0" />
              </button>
            ))}
          </div>
        )}

        {streaming && statusLines.length === 0 && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-2.5 shadow-sm">
              <span className="inline-flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-gray-200 bg-white p-3">
        <div className="flex gap-2">
          <input
            className="flex-1 border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
            placeholder={connected ? "Message resume agent…" : "Connecting…"}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && submit()}
            disabled={!connected || streaming}
          />
          <button
            onClick={() => submit()}
            disabled={!connected || streaming || !input.trim()}
            className="p-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl disabled:opacity-40 transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
