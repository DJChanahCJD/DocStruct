import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { MouseEvent } from "react";
import { MoreVertical, RotateCcw, Trash2 } from "lucide-react";
import type { DocumentRecord } from "@/lib/api";

const statusColor: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-700",
  processing: "bg-amber-100 text-amber-700",
  failed: "bg-red-100 text-red-700",
  pending: "bg-slate-100 text-slate-600",
};

interface DocCardProps {
  doc: DocumentRecord;
  selected: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onReindex: () => void;
}

export function DocCard({
  doc,
  selected,
  onSelect,
  onDelete,
  onReindex,
}: DocCardProps) {
  return (
    <div
      onClick={onSelect}
      className={`group relative cursor-pointer rounded-lg border px-3 py-2.5 transition-all ${
        selected
          ? "border-blue-500 bg-blue-50 shadow-sm"
          : "border-transparent hover:bg-muted/50"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{doc.filename}</div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <Badge variant="secondary" className="text-[10px] uppercase">
              {doc.doc_type || "unknown"}
            </Badge>
            <span
              className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${statusColor[doc.status] ?? statusColor.pending}`}
            >
              {doc.status}
            </span>
          </div>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger
            className="inline-flex h-7 w-7 items-center justify-center rounded-md opacity-0 hover:bg-muted group-hover:opacity-100"
            onClick={(e: MouseEvent<HTMLButtonElement>) => e.stopPropagation()}
          >
            <MoreVertical className="h-4 w-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onClick={(e: MouseEvent<HTMLDivElement>) => {
                e.stopPropagation();
                onReindex();
              }}
            >
              <RotateCcw className="mr-2 h-3.5 w-3.5" />
              重建索引
            </DropdownMenuItem>
            <DropdownMenuItem
              className="text-destructive"
              onClick={(e: MouseEvent<HTMLDivElement>) => {
                e.stopPropagation();
                onDelete();
              }}
            >
              <Trash2 className="mr-2 h-3.5 w-3.5" />
              删除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
