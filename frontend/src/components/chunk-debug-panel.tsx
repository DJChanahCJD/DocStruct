import { useEffect, useMemo, useState } from "react";
import { Copy, FileSearch, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useDocumentChunks } from "@/hooks/use-api";
import type { DocumentChunkDebug } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ChunkDebugPanelProps {
  docId: number | null;
}

/**
 * Render a read-only debug view of the chunks sent to extraction.
 */
export function ChunkDebugPanel({ docId }: ChunkDebugPanelProps) {
  const { data, isLoading, isError } = useDocumentChunks(docId);
  const chunks = data?.chunks ?? [];
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null);
  const selectedChunk = useMemo(
    () => chunks.find((chunk) => chunk.chunk_id === selectedChunkId) ?? chunks[0] ?? null,
    [chunks, selectedChunkId],
  );

  useEffect(() => {
    setSelectedChunkId(null);
  }, [docId]);

  useEffect(() => {
    if (selectedChunkId && chunks.some((chunk) => chunk.chunk_id === selectedChunkId)) {
      return;
    }
    setSelectedChunkId(chunks[0]?.chunk_id ?? null);
  }, [chunks, selectedChunkId]);

  const handleCopyChunk = async () => {
    if (!selectedChunk) {
      return;
    }
    try {
      await navigator.clipboard.writeText(selectedChunk.markdown);
      toast.success("Chunk 内容已复制");
    } catch {
      toast.error("复制失败，请手动复制");
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        加载分块数据中...
      </div>
    );
  }

  if (isError || chunks.length === 0) {
    return <ChunkEmptyState />;
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            Chunk Debug
          </p>
          <h3 className="mt-1 text-base font-semibold text-foreground">当前分块规则输出</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="rounded-full border px-2.5 py-1">{data?.chunk_count ?? 0} 个 chunk</span>
          <span className="rounded-full border px-2.5 py-1">上限 {data?.chunk_max_chars ?? 0} 字符</span>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 gap-4 p-5 xl:grid-cols-[minmax(260px,0.72fr)_minmax(0,1.28fr)]">
        <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border bg-muted/15 shadow-sm">
          <div className="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-3">
            <p className="text-xs font-medium tracking-[0.16em] text-muted-foreground uppercase">
              分块列表
            </p>
            <span className="text-xs text-muted-foreground">
              忽略 {data?.ignored_sections.length ?? 0} 条规则
            </span>
          </div>
          <ScrollArea className="min-h-0 flex-1">
            <div className="flex flex-col gap-2 p-3">
              {chunks.map((chunk, index) => (
                <ChunkRow
                  key={chunk.chunk_id}
                  index={index}
                  chunk={chunk}
                  selected={chunk.chunk_id === selectedChunk?.chunk_id}
                  onClick={() => setSelectedChunkId(chunk.chunk_id)}
                />
              ))}
            </div>
          </ScrollArea>
        </section>

        <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border bg-background shadow-sm">
          <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
            <div className="min-w-0">
              <p className="font-mono text-xs text-muted-foreground">{selectedChunk?.chunk_id}</p>
              <p className="mt-1 truncate text-sm font-medium text-foreground">
                {formatSectionPath(selectedChunk?.section_path)}
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleCopyChunk}
              disabled={!selectedChunk}
            >
              <Copy data-icon="inline-start" />
              复制
            </Button>
          </div>
          <ScrollArea className="min-h-0 flex-1">
            <pre className="whitespace-pre-wrap break-words p-4 font-mono text-xs leading-5 text-foreground">
              {selectedChunk?.markdown}
            </pre>
          </ScrollArea>
        </section>
      </div>
    </div>
  );
}

/**
 * Render one selectable chunk summary row.
 */
function ChunkRow({
  index,
  chunk,
  selected,
  onClick,
}: {
  index: number;
  chunk: DocumentChunkDebug;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full flex-col gap-2 rounded-md border px-3 py-2.5 text-left transition-colors",
        selected ? "border-primary bg-primary/5" : "border-border bg-background hover:bg-muted/45",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-xs font-medium text-foreground">
          #{String(index + 1).padStart(2, "0")}
        </span>
        <span className="text-[11px] text-muted-foreground">{formatPageRange(chunk)}</span>
      </div>
      <p className="line-clamp-2 text-sm font-medium text-foreground">
        {formatSectionPath(chunk.section_path)}
      </p>
      <div className="flex flex-wrap gap-1.5 text-[11px] text-muted-foreground">
        <span className="rounded-full border px-2 py-0.5">{chunk.markdown_chars} 字符</span>
        <span className="rounded-full border px-2 py-0.5">{chunk.element_count} 元素</span>
      </div>
    </button>
  );
}

/**
 * Render the empty state for unparsed or chunkless documents.
 */
function ChunkEmptyState() {
  return (
    <div className="flex h-full min-h-0 flex-col items-center justify-center gap-3 px-8 text-center text-sm text-muted-foreground">
      <FileSearch className="h-8 w-8 opacity-40" />
      <div>
        <p className="font-medium text-foreground">暂无分块数据</p>
        <p className="mt-1">文档解析完成并生成 IR 后，这里会显示当前分块内容。</p>
      </div>
    </div>
  );
}

/**
 * Format a section path for compact display.
 */
function formatSectionPath(sectionPath: string[] | undefined): string {
  if (!sectionPath || sectionPath.length === 0) {
    return "无章节路径";
  }
  return sectionPath.join(" > ");
}

/**
 * Format page start and end into a short label.
 */
function formatPageRange(chunk: DocumentChunkDebug): string {
  if (chunk.page_start === null && chunk.page_end === null) {
    return "无页码";
  }
  if (chunk.page_start === chunk.page_end || chunk.page_end === null) {
    return `P${chunk.page_start}`;
  }
  if (chunk.page_start === null) {
    return `P${chunk.page_end}`;
  }
  return `P${chunk.page_start}-${chunk.page_end}`;
}
