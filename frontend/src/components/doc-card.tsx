import type { MouseEvent, ReactNode } from "react";
import {
  AlertCircle,
  Activity,
  Bug,
  Clock,
  Cpu,
  FileText,
  Hash,
  Layers3,
  MoreVertical,
  RefreshCw,
  Trash2,
} from "lucide-react";

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
import type { DocumentListItem } from "@/lib/api";

const statusColor: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-700",
  uploaded: "bg-amber-100 text-amber-700",
  parsing: "bg-amber-100 text-amber-700",
  extracting: "bg-amber-100 text-amber-700",
  processing: "bg-amber-100 text-amber-700",
  failed: "bg-red-100 text-red-700",
  pending: "bg-slate-100 text-slate-600",
};

const statusLabel: Record<string, string> = {
  completed: "已完成",
  uploaded: "已上传",
  parsing: "解析中",
  extracting: "提取中",
  processing: "处理中",
  failed: "失败",
  pending: "待处理",
};

interface DocCardProps {
  doc: DocumentListItem;
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
              <div className="truncate text-sm font-medium">{doc.title}</div>
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
              {doc.status !== "completed" && doc.status !== "failed" && (
                <div className="mt-1 text-[11px] text-muted-foreground">
                  {doc.status === "uploaded"
                    ? "等待开始处理"
                    : doc.status === "parsing"
                      ? "正在解析原文"
                      : doc.status === "extracting"
                        ? "正在提取结构化结果"
                        : "处理中"}
                </div>
              )}
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
                    {doc.status === "failed" && doc.has_raw_text && onRetry && (
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
                      onClick={(event: MouseEvent<HTMLDivElement>) => {
                        event.stopPropagation();
                        window.open(`/chunk-debug.html?docId=${doc.id}`, "_blank");
                      }}
                    >
                      <Bug className="mr-2 h-3.5 w-3.5" />
                      调试分块
                    </DropdownMenuItem>
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
          <div className="truncate pr-1 text-sm font-semibold" title={doc.title}>
            {doc.title}
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
            <div className="rounded-md bg-muted/50 px-2.5 py-2 text-xs leading-5 text-muted-foreground">
              <div className="mb-1 font-medium text-foreground">摘要</div>
              <div className="line-clamp-4">{formatSummary(doc)}</div>
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              <DocMetricItem
                icon={<Cpu className="h-3 w-3" />}
                label="模型"
                value={formatModel(doc)}
              />
              <DocMetricItem
                icon={<Activity className="h-3 w-3" />}
                label="置信度"
                value={formatConfidence(doc)}
              />
              <DocMetricItem
                icon={<Layers3 className="h-3 w-3" />}
                label="Chunks"
                value={formatChunks(doc)}
              />
              <DocMetricItem
                icon={<FileText className="h-3 w-3" />}
                label="IR"
                value={formatIr(doc)}
              />
            </div>
            <DocMetaItem
              icon={<Hash className="h-3 w-3" />}
              label="文档 ID"
              value={String(doc.id)}
            />
            <DocMetaItem
              icon={<FileText className="h-3 w-3" />}
              label="Markdown"
              value={doc.has_raw_text ? "已生成" : "未生成"}
            />
            <DocMetaItem
              icon={<Clock className="h-3 w-3" />}
              label="创建"
              value={new Date(doc.created_at).toLocaleString("zh-CN", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
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

function DocMetricItem({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0 rounded-md border bg-background px-2 py-1.5 text-xs">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        {icon}
        <span>{label}</span>
      </div>
      <div className="mt-0.5 truncate font-medium text-foreground">{value}</div>
    </div>
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

function formatSummary(doc: DocumentListItem): string {
  if (doc.summary?.trim()) {
    return doc.summary.trim();
  }
  if (getMetaText(doc, "summary_error")) {
    return "摘要生成失败";
  }
  return "暂无摘要";
}

function formatModel(doc: DocumentListItem): string {
  return getMetaText(doc, "llm_model") || "-";
}

function formatConfidence(doc: DocumentListItem): string {
  const confidence = getMetaNumber(doc, "confidence");
  return confidence > 0 ? `${Math.round(confidence * 100)}%` : "-";
}

function formatChunks(doc: DocumentListItem): string {
  const chunkCount = getMetaNumber(doc, "chunk_count");
  const failedChunks = getMetaNumber(doc, "failed_chunks");
  if (chunkCount <= 0) {
    return "-";
  }
  return failedChunks > 0 ? `${chunkCount}/${failedChunks} 失败` : String(chunkCount);
}

function formatIr(doc: DocumentListItem): string {
  const elements = getMetaNumber(doc, "element_count");
  const sections = getMetaNumber(doc, "section_count");
  if (elements <= 0 && sections <= 0) {
    return doc.has_document_ir ? "已生成" : "-";
  }
  return `${elements} 元素 / ${sections} 章`;
}

function getMetaText(doc: DocumentListItem, key: string): string {
  const meta = doc.extraction_meta;
  if (!isRecord(meta)) {
    return "";
  }
  const value = meta[key];
  return typeof value === "string" ? value : "";
}

function getMetaNumber(doc: DocumentListItem, key: string): number {
  const meta = doc.extraction_meta;
  if (!isRecord(meta)) {
    return 0;
  }
  const value = meta[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
