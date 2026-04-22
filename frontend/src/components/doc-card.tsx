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
import { MoreVertical, RotateCcw, Trash2, FileText, Link2, Bot, Clock } from "lucide-react";
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

function getStatusLabel(status: string) {
  return statusLabel[status] ?? status;
}

function getSourceTypeLabel(sourceType: string | null) {
  if (!sourceType) return "-";
  return sourceTypeLabel[sourceType] ?? sourceType;
}

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
            </div>

            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <Badge variant="secondary" className="text-[10px] uppercase">
                {doc.doc_type || "unknown"}
              </Badge>
              <span
                className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${statusColor[doc.status] ?? statusColor.pending}`}
              >
                {getStatusLabel(doc.status)}
              </span>
            </div>
          </div>

          {/* 右端操作区：ID / 更多按钮 */}
          <div className="relative shrink-0 h-6 w-6 flex items-center justify-center">
            {/* ID - 默认显示，hover 隐藏 */}
            <span 
              className={`absolute text-xs font-mono text-muted-foreground/60 transition-all duration-150 ease-out group-hover:opacity-0 group-hover:scale-90 ${
                selected ? "text-primary/60" : ""
              }`}
            >
              #{doc.id}
            </span>
            
            {/* 菜单按钮 - hover 显示 */}
            <div className="absolute inset-0 flex items-center justify-center opacity-0 scale-90 transition-all duration-150 ease-out group-hover:opacity-100 group-hover:scale-100">
              <DropdownMenu>
                <DropdownMenuTrigger
                  className="inline-flex h-6 w-6 items-center justify-center rounded-md hover:bg-muted transition-colors"
                  onClick={(e: MouseEvent<HTMLButtonElement>) => e.stopPropagation()}
                >
                  <MoreVertical className="h-4 w-4 text-muted-foreground" />
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
        </div>
      </TooltipTrigger>

      <TooltipContent side="right" className="max-w-72 p-3">
        <div className="space-y-2">
          {/* 标题：文件名 */}
          <div className="font-semibold text-sm truncate pr-1" title={doc.filename}>
            {doc.filename}
          </div>
          
          {/* 元信息行：ID · 类型 · 状态 */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="font-mono text-muted-foreground">#{doc.id}</span>
            <span className="text-muted-foreground/50">·</span>
            <Badge variant="secondary" className="text-[10px] h-4 px-1">
              {doc.doc_type || "unknown"}
            </Badge>
            <span className="text-muted-foreground/50">·</span>
            <span className={`text-[10px] font-medium ${statusColor[doc.status]?.split(' ')[1] ?? 'text-slate-600'}`}>
              {getStatusLabel(doc.status)}
            </span>
          </div>
          
          {/* 分隔线 */}
          <div className="border-t border-border/60 my-1.5" />
          
          {/* 次要信息 */}
          <div className="space-y-1">
            <DocMetaItem 
              icon={<FileText className="h-3 w-3" />}
              label="来源"
              value={getSourceTypeLabel(doc.source_type)}
            />
            {doc.source_type === "url" && doc.source_url && (
              <DocMetaItem 
                icon={<Link2 className="h-3 w-3" />}
                label="URL"
                value={doc.source_url}
                truncate
              />
            )}
            <DocMetaItem 
              icon={<Bot className="h-3 w-3" />}
              label="模型"
              value={doc.llm_model ?? "-"}
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
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

/**
 * 渲染 Tooltip 内的元数据项（图标 + 标签 + 值）。
 */
function DocMetaItem({
  icon,
  label,
  value,
  truncate = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | null;
  truncate?: boolean;
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground flex items-center">
        {icon}
      </span>
      <span className="text-muted-foreground">{label}</span>
      <span className={`font-medium ${truncate ? 'truncate flex-1' : ''}`}>
        {value ?? "-"}
      </span>
    </div>
  );
}
