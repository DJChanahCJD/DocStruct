import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { MouseEvent } from "react";
import { MoreVertical, RotateCcw, Trash2 } from "lucide-react";
import type { DocumentRecord } from "@/lib/api";

const statusColor: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-700",
  processing: "bg-amber-100 text-amber-700",
  failed: "bg-red-100 text-red-700",
  pending: "bg-slate-100 text-slate-600",
};

const statusLabel: Record<string, string> = {
  completed: "已完成",
  processing: "处理中",
  failed: "失败",
  pending: "待处理",
};

const sourceTypeLabel: Record<string, string> = {
  file: "文件上传",
  url: "URL 抓取",
};

interface DocCardProps {
  doc: DocumentRecord;
  selected: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onReindex: () => void;
}

/**
 * 返回面向用户显示的文档状态文案。
 */
function getStatusLabel(status: string) {
  return statusLabel[status] ?? status;
}

/**
 * 返回面向用户显示的文档来源文案。
 */
function getSourceTypeLabel(sourceType: string | null) {
  if (!sourceType) return "-";
  return sourceTypeLabel[sourceType] ?? sourceType;
}

/**
 * 渲染侧栏文档卡片，并在 hover 时展示基础元数据。
 */
export function DocCard({
  doc,
  selected,
  onSelect,
  onDelete,
  onReindex,
}: DocCardProps) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <div
            onClick={onSelect}
            className={`group relative cursor-pointer rounded-lg border px-3 py-2.5 transition-all ${
              selected
                ? "border-primary bg-primary/10 ring-1 ring-primary/20"
                : "border-transparent hover:border-border hover:bg-muted/50"
            }`}
          />
        }
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium">
              {doc.filename}
              <span className="ml-1 font-mono text-sm text-muted-foreground/60">
                #{doc.id}
              </span>
            </div>

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
      </TooltipTrigger>

      <TooltipContent side="right" className="max-w-80">
        <div className="flex flex-col gap-1.5">
          <DocMetaRow label="文件名" value={doc.filename} />
          <DocMetaRow label="类型" value={doc.doc_type ?? "-"} />
          <DocMetaRow label="来源" value={getSourceTypeLabel(doc.source_type)} />
          <DocMetaRow label="状态" value={getStatusLabel(doc.status)} />
          <DocMetaRow label="处理模型" value={doc.llm_model ?? "-"} />
        </div>
      </TooltipContent>

    </Tooltip>
  );
}

/**
 * 渲染 Tooltip 内的单行元数据。
 */
function DocMetaRow({
  label,
  value,
}: {
  label: string;
  value: string | null;
}) {
  return (
    <div className="grid grid-cols-[auto_1fr] items-start gap-2 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="break-all font-medium text-background">{value ?? "-"}</span>
    </div>
  );
}

