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

const COLUMNS: { key: keyof Pipeline; label: string; color: string }[] = [
  { key: "saved", label: "Saved", color: "bg-gray-50 border-gray-200" },
  { key: "applied", label: "Applied", color: "bg-blue-50 border-blue-200" },
  { key: "interview", label: "Interview", color: "bg-yellow-50 border-yellow-200" },
  { key: "offer", label: "Offer", color: "bg-green-50 border-green-200" },
];

interface KanbanCardProps {
  job: Job;
  onClick: () => void;
}

function KanbanCard({ job, onClick }: KanbanCardProps) {
  const hash = job.url_hash ?? "";
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: hash });

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      {...attributes}
      {...listeners}
      onClick={onClick}
      className={`bg-white rounded-lg border border-gray-200 p-3 cursor-grab active:cursor-grabbing shadow-sm hover:shadow transition-shadow ${
        isDragging ? "opacity-50" : ""
      }`}
    >
      <p className="font-medium text-sm text-gray-900 leading-snug truncate">{job.title}</p>
      <p className="text-xs text-gray-500 truncate mt-0.5">{job.company}</p>
      {job.fit_score !== undefined && (
        <div className="mt-2">
          <FitBar value={job.fit_score} />
        </div>
      )}
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
    <div className="w-80 bg-white border-l border-gray-200 flex flex-col shrink-0">
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <h3 className="font-semibold text-gray-900 truncate">{job.title}</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none ml-2">
          ×
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <p className="text-sm font-medium text-gray-700">{job.company}</p>
        {job.location && <p className="text-sm text-gray-500">{job.location}</p>}
        {job.fit_score !== undefined && (
          <div>
            <p className="text-xs text-gray-400 mb-1">Fit score</p>
            <FitBar value={job.fit_score} />
          </div>
        )}
        {job.description && (
          <div>
            <p className="text-xs text-gray-400 mb-1">Description</p>
            <p className="text-xs text-gray-600 leading-relaxed line-clamp-6">{job.description}</p>
          </div>
        )}
        <div>
          <p className="text-xs text-gray-400 mb-1">Notes</p>
          <textarea
            className="w-full border border-gray-200 rounded-lg p-2 text-sm text-gray-700 resize-none focus:outline-none focus:ring-2 focus:ring-blue-300"
            rows={5}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add notes…"
          />
          <button
            onClick={() => onNotesSave(hash, notes)}
            className="mt-1 w-full text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-1.5 transition-colors"
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
                className={`rounded-xl border flex flex-col w-64 shrink-0 ${col.color}`}
              >
                <div className="p-3 font-semibold text-sm text-gray-700 border-b border-inherit flex items-center justify-between">
                  {col.label}
                  <span className="text-xs bg-white rounded-full px-2 py-0.5 border border-gray-200 text-gray-500">
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
