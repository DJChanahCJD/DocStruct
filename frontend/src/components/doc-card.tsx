import type { MouseEvent, ReactNode } from "react";
import { AlertCircle, Clock, FileText, FolderOpen, Hash, MoreVertical, RefreshCw, Trash2 } from "lucide-react";

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

interface DocCardProps {
  doc: DocumentRecord;
  selected: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRetry?: () => void;
}

function getStatusLabel(status: string) {
  return statusLabel[status] ?? status;
}

export function DocCard({ doc, selected, onSelect, onDelete, onRetry }: DocCardProps) {
  return (
    <Tooltip>
      <TooltipTrigger render={<div />} className="block w-full">
        <div
          onClick={onSelect}
          className={`w-full group relative cursor-pointer rounded-lg border px-3 py-2.5 transition-all ${
            selected
              ? "border-primary bg-primary/10 ring-1 ring-primary/20"
              : "border-transparent hover:border-border hover:bg-muted/50"
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
                  className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                    statusColor[doc.status] ?? statusColor.pending
                  }`}
                >
                  {getStatusLabel(doc.status)}
                </span>
              </div>
            </div>

            <div className="relative flex h-6 w-6 shrink-0 items-center justify-center">
              <span
                className={`absolute text-xs font-mono text-muted-foreground/60 transition-all duration-150 ease-out group-hover:scale-90 group-hover:opacity-0 ${
                  selected ? "text-primary/60" : ""
                }`}
              >
                #{doc.id}
              </span>

              <div className="absolute inset-0 flex scale-90 items-center justify-center opacity-0 transition-all duration-150 ease-out group-hover:scale-100 group-hover:opacity-100">
                <DropdownMenu>
                  <DropdownMenuTrigger
                    className="inline-flex h-6 w-6 items-center justify-center rounded-md transition-colors hover:bg-muted"
                    onClick={(event: MouseEvent<HTMLButtonElement>) => event.stopPropagation()}
                  >
                    <MoreVertical className="h-4 w-4 text-muted-foreground" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {doc.status === "failed" && doc.parsed_content && onRetry && (
                      <DropdownMenuItem
                        onClick={(event: MouseEvent<HTMLDivElement>) => {
                          event.stopPropagation();
                          onRetry();
                        }}
                      >
                        <RefreshCw className="mr-2 h-3.5 w-3.5" />
                        重试提取
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem
                      className="text-destructive"
                      onClick={(event: MouseEvent<HTMLDivElement>) => {
                        event.stopPropagation();
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
          </div>
        </div>
      </TooltipTrigger>

      <TooltipContent side="right" className="max-w-72 p-3">
        <div className="space-y-2">
          <div className="truncate pr-1 text-sm font-semibold" title={doc.filename}>
            {doc.filename}
          </div>

          <div className="flex items-center gap-1.5 text-xs">
            <span className="font-mono text-muted-foreground">#{doc.id}</span>
            <span className="text-muted-foreground/50">·</span>
            <Badge variant="secondary" className="h-4 px-1 text-[10px]">
              {doc.doc_type || "unknown"}
            </Badge>
            <span className="text-muted-foreground/50">·</span>
            <span
              className={`text-[10px] font-medium ${
                statusColor[doc.status]?.split(" ")[1] ?? "text-slate-600"
              }`}
            >
              {getStatusLabel(doc.status)}
            </span>
          </div>

          <div className="my-1.5 border-t border-border/60" />

          <div className="space-y-1">
            <DocMetaItem
              icon={<Hash className="h-3 w-3" />}
              label="文档 ID"
              value={String(doc.id)}
            />
            <DocMetaItem
              icon={<FileText className="h-3 w-3" />}
              label="Markdown"
              value={`${doc.parsed_content?.length ?? 0} 字符`}
            />
            <DocMetaItem
              icon={<Clock className="h-3 w-3" />}
              label="上传"
              value={new Date(doc.upload_time).toLocaleString("zh-CN", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            />
            <DocMetaItem
              icon={<FolderOpen className="h-3 w-3" />}
              label="路径"
              value={doc.stored_path}
            />
            {doc.error_message && (
              <div className="rounded-md border border-destructive/30 bg-destructive/5 px-2.5 py-2 text-xs text-destructive">
                <div className="mb-1 flex items-center gap-1.5 font-medium">
                  <AlertCircle className="h-3 w-3" />
                  处理异常
                </div>
                <div className="line-clamp-4 break-all">{doc.error_message}</div>
              </div>
            )}
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

function DocMetaItem({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string | null;
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="flex items-center text-muted-foreground">{icon}</span>
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value ?? "-"}</span>
    </div>
  );
}
