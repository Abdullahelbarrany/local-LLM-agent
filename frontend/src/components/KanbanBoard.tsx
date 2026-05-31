import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";
import type { Job } from "../hooks/useJobSearch";
import type { Pipeline } from "../hooks/usePipeline";
import { FitBar } from "./FitBar";

const COLUMNS: { key: keyof Pipeline; label: string }[] = [
  { key: "saved",     label: "Saved" },
  { key: "applied",   label: "Applied" },
  { key: "interview", label: "Interview" },
  { key: "offer",     label: "Offer" },
];

const SOURCE_COLORS: Record<string, string> = {
  LinkedIn:       "bg-blue-100 text-blue-700 border border-blue-200",
  Indeed:         "bg-violet-100 text-violet-700 border border-violet-200",
  Glassdoor:      "bg-green-100 text-green-700 border border-green-200",
  Wuzzuf:         "bg-orange-100 text-orange-700 border border-orange-200",
  Bayt:           "bg-red-100 text-red-700 border border-red-200",
  NaukriGulf:     "bg-pink-100 text-pink-700 border border-pink-200",
  Remotive:       "bg-teal-100 text-teal-700 border border-teal-200",
  WeWorkRemotely: "bg-cyan-100 text-cyan-700 border border-cyan-200",
  Jobicy:         "bg-purple-100 text-purple-700 border border-purple-200",
  Otta:           "bg-lime-100 text-lime-700 border border-lime-200",
  Himalayas:      "bg-amber-100 text-amber-700 border border-amber-200",
  Wellfound:      "bg-fuchsia-100 text-fuchsia-700 border border-fuchsia-200",
};

interface KanbanCardProps {
  job: Job;
  onClick: () => void;
}

function KanbanCard({ job, onClick }: KanbanCardProps) {
  const hash = job.url_hash ?? "";
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: hash });
  const sourceColor = SOURCE_COLORS[job.source] ?? "bg-slate-100 text-slate-600 border border-slate-200";

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      {...attributes}
      {...listeners}
      onClick={onClick}
      className={`bg-white border border-slate-200 rounded-xl p-3 cursor-grab active:cursor-grabbing transition-all duration-150 hover:border-green-400 hover:shadow-sm ${
        isDragging
          ? "opacity-50 ring-2 ring-green-400/60 shadow-md"
          : ""
      }`}
    >
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${sourceColor}`}>
          {job.source}
        </span>
      </div>
      <p className="font-medium text-sm text-slate-800 leading-snug truncate">{job.title}</p>
      <p className="text-xs text-slate-500 truncate mt-0.5">{job.company}</p>
    </div>
  );
}

interface SidePanelProps {
  job: Job;
  onClose: () => void;
  onNotesSave: (hash: string, notes: string) => void;
}

function SidePanel({ job, onClose, onNotesSave }: SidePanelProps) {
  const hash = job.url_hash ?? "";
  const [notes, setNotes] = useState((job as unknown as Record<string, unknown>).notes as string ?? "");

  return (
    <div className="w-80 bg-white border-l border-slate-200 flex flex-col shrink-0 shadow-sm">
      <div className="flex items-center justify-between p-4 border-b border-slate-100">
        <h3 className="font-semibold text-slate-800 text-sm truncate">{job.title}</h3>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-700 text-lg leading-none ml-2 transition-colors"
        >
          ×
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div>
          <p className="text-sm font-medium text-slate-800">{job.company}</p>
          {job.location && <p className="text-sm text-slate-500 mt-0.5">{job.location}</p>}
        </div>
        {job.fit_score !== undefined && (
          <div>
            <p className="text-[10px] text-slate-400 uppercase tracking-widest mb-1.5">Fit score</p>
            <FitBar value={job.fit_score} />
          </div>
        )}
        {job.description && (
          <div>
            <p className="text-[10px] text-slate-400 uppercase tracking-widest mb-1.5">Description</p>
            <p className="text-xs text-slate-500 leading-relaxed line-clamp-6">{job.description}</p>
          </div>
        )}
        <div>
          <p className="text-[10px] text-slate-400 uppercase tracking-widest mb-1.5">Notes</p>
          <textarea
            className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-sm text-slate-800 placeholder:text-slate-400 resize-none focus:outline-none focus:border-green-500 transition-colors"
            rows={5}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add notes…"
          />
          <button
            onClick={() => onNotesSave(hash, notes)}
            className="mt-2 w-full text-xs bg-green-600 hover:bg-green-500 text-white rounded-lg py-2 font-medium transition-all hover:shadow-md"
          >
            Save notes
          </button>
        </div>
      </div>
    </div>
  );
}

interface KanbanBoardProps {
  pipeline: Pipeline;
  onMove: (urlHash: string, newStatus: string) => void;
  onNotesSave: (urlHash: string, notes: string) => void;
}

export function KanbanBoard({ pipeline, onMove, onNotesSave }: KanbanBoardProps) {
  const [selected, setSelected] = useState<Job | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  // Build a flat map from id → column key
  const idToColumn: Record<string, keyof Pipeline> = {};
  for (const col of COLUMNS) {
    for (const job of pipeline[col.key]) {
      if (job.url_hash) idToColumn[job.url_hash] = col.key;
    }
  }

  const handleDragEnd = (evt: DragEndEvent) => {
    const { active, over } = evt;
    if (!over || active.id === over.id) return;
    const draggedHash = String(active.id);
    // over.id could be a column key or a card id — detect which
    const targetCol = COLUMNS.find((c) => c.key === String(over.id));
    if (targetCol) {
      onMove(draggedHash, targetCol.key);
    } else {
      const destCol = idToColumn[String(over.id)];
      if (destCol) onMove(draggedHash, destCol);
    }
  };

  return (
    <div className="flex flex-1 overflow-hidden">
      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <div className="flex gap-4 flex-1 overflow-x-auto p-4">
          {COLUMNS.map((col) => {
            const jobs = pipeline[col.key];
            const ids = jobs.map((j) => j.url_hash ?? j.url);
            return (
              <div
                key={col.key}
                className="bg-slate-100 border border-slate-200 rounded-2xl flex flex-col w-64 shrink-0"
              >
                <div className="p-3 border-b border-slate-200 flex items-center justify-between">
                  <span className="text-xs text-slate-600 uppercase tracking-widest font-semibold">
                    {col.label}
                  </span>
                  <span className="text-xs bg-white text-slate-500 border border-slate-200 rounded-full px-2 py-0.5">
                    {jobs.length}
                  </span>
                </div>
                <SortableContext items={ids} strategy={verticalListSortingStrategy}>
                  <div className="flex flex-col gap-2 p-2 flex-1 min-h-[120px]">
                    {jobs.map((job) => (
                      <KanbanCard
                        key={job.url_hash ?? job.url}
                        job={job}
                        onClick={() => setSelected(job)}
                      />
                    ))}
                  </div>
                </SortableContext>
              </div>
            );
          })}
        </div>
      </DndContext>
      {selected && (
        <SidePanel
          job={selected}
          onClose={() => setSelected(null)}
          onNotesSave={onNotesSave}
        />
      )}
    </div>
  );
}
