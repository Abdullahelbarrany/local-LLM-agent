import { RefreshCw } from "lucide-react";
import { useEffect } from "react";
import { KanbanBoard } from "../components/KanbanBoard";
import { usePipeline } from "../hooks/usePipeline";

export function PipelineView() {
  const { pipeline, loading, load, moveCard, updateNotes } = usePipeline();

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <h2 className="font-semibold text-gray-800">Application Pipeline</h2>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 disabled:opacity-40 transition-colors"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>
      <div className="flex-1 overflow-hidden flex">
        <KanbanBoard
          pipeline={pipeline}
          onMove={moveCard}
          onNotesSave={updateNotes}
        />
      </div>
    </div>
  );
}
