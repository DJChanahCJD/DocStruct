import { useState, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { useDocument, useUpdateDocument } from "@/hooks/use-api";
import { ReExtractPanel } from "@/components/re-extract-panel";
import { FieldJsonView } from "@/components/field-json-view";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import type { CitationItem } from "@/lib/api";

const Markdown = ReactMarkdown as React.FC<{
  remarkPlugins?: unknown[];
  children?: string;
}>;

interface DocPreviewPanelProps {
  docId: number | null;
  mode: "preview" | "citation";
  citationSnippet?: CitationItem | null;
}

export function DocPreviewPanel({ docId, mode, citationSnippet }: DocPreviewPanelProps) {
  const { data: doc, isLoading } = useDocument(docId);
  const updateDoc = useUpdateDocument(docId ?? 0);

  // idle | reextracting  两种互斥的 JSON 面板模式（行级编辑由 FieldInlineEditor 管理）
  const [jsonMode, setJsonMode] = useState<"idle" | "reextracting">("idle");

  useEffect(() => {
    setJsonMode("idle");
  }, [docId]);

  /** ReExtractPanel 全量重提取回调：应用新结果并持久化 */
  const handleReExtractApply = async (newData: Record<string, unknown>) => {
    await updateDoc.mutateAsync({ extracted_data: newData });
    setJsonMode("idle");
  };

  /** 行级编辑/追问单字段应用回调：merge 单字段后持久化 */
  const handleFieldApply = async (fieldKey: string, newValue: unknown) => {
    const current = (doc?.extracted_data ?? {}) as Record<string, unknown>;
    const merged = { ...current, [fieldKey]: newValue };
    await updateDoc.mutateAsync({ extracted_data: merged });
    toast.success(`字段「${fieldKey}」已更新`);
  };

  if (!docId) return null;

  // --- 状态处理：加载中 ---
  if (isLoading) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center bg-background text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span className="mt-3 text-sm tracking-wide">加载中...</span>
      </div>
    );
  }

  // --- 状态处理：无数据 ---
  if (!doc) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-background text-muted-foreground">
        <p className="text-sm">文档不存在</p>
      </div>
    );
  }

  // --- 主渲染逻辑 ---
  return (
    <div className="flex h-full w-full flex-1 flex-col overflow-hidden bg-background">
      <Tabs defaultValue="json" className="flex flex-1 flex-col overflow-hidden">

        {/* 顶部 Tab 导航 */}
        <div className="shrink-0 border-b px-4 py-2">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="json">JSON</TabsTrigger>
            <TabsTrigger value="raw">原文</TabsTrigger>
          </TabsList>
        </div>

        {/* 引用片段 (仅在 citation 模式下显示) */}
        {mode === "citation" && citationSnippet && (
          <div className="shrink-0 border-b bg-muted/30 px-5 py-4">
            <div className="border-l-4 border-primary pl-4">
              <div className="mb-1 text-xs font-semibold tracking-wider text-primary">
                引用片段
              </div>
              {citationSnippet.title_path && (
                <p className="mb-1.5 text-xs text-muted-foreground/80">
                  {citationSnippet.title_path}
                </p>
              )}
              <p className="text-sm leading-relaxed text-foreground/90">
                {citationSnippet.snippet}
              </p>
            </div>
          </div>
        )}

        {/* 错误提示区 (全局错误) */}
        {doc.error_message && (
          <div className="shrink-0 bg-destructive/10 px-4 py-3 text-sm text-destructive flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            <span>{doc.error_message}</span>
          </div>
        )}

        {/* 原文视图 */}
        <TabsContent value="raw" className="m-0 flex-1 overflow-hidden focus-visible:outline-none">
          <ScrollArea className="h-full px-5 py-4">
            <div className="prose prose-sm dark:prose-invert max-w-none leading-relaxed">
              <Markdown remarkPlugins={[remarkGfm]}>
                {doc.parsed_content || "暂无原文内容"}
              </Markdown>
            </div>
          </ScrollArea>
        </TabsContent>

        {/* JSON 视图 */}
        <TabsContent value="json" className="m-0 flex-1 overflow-hidden focus-visible:outline-none">
          <ScrollArea className="h-full px-5 py-4">

            {/* 重新提取模式 */}
            {jsonMode === "reextracting" && (
              <div className="flex flex-col gap-4">
                <pre className="overflow-x-auto whitespace-pre-wrap rounded-md bg-muted/50 p-4 font-mono text-sm leading-relaxed opacity-50">
                  {doc.extracted_data
                    ? JSON.stringify(doc.extracted_data, null, 2)
                    : "暂无结构化数据"}
                </pre>
                <ReExtractPanel
                  docId={doc.id}
                  currentData={doc.extracted_data ?? {}}
                  onApply={handleReExtractApply}
                  onCancel={() => setJsonMode("idle")}
                />
              </div>
            )}

            {/* 只读模式（idle） */}
            {jsonMode === "idle" && (
              <div className="group relative">
                <div className="absolute right-2 top-2 flex gap-1.5 opacity-0 transition-opacity group-hover:opacity-100 z-10">
                  <Button
                    size="sm"
                    variant="secondary"
                    className="h-8"
                    onClick={() => setJsonMode("reextracting")}
                  >
                    <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                    全量重提取
                  </Button>
                </div>
                {doc.extracted_data && typeof doc.extracted_data === "object" && !Array.isArray(doc.extracted_data) ? (
                  <div className="rounded-md bg-muted/50 p-4">
                    <FieldJsonView
                      data={doc.extracted_data as Record<string, unknown>}
                      docId={doc.id}
                      onFieldApply={handleFieldApply}
                    />
                  </div>
                ) : (
                  <pre className="overflow-x-auto whitespace-pre-wrap rounded-md bg-muted/50 p-4 font-mono text-sm leading-relaxed">
                    {doc.extracted_data
                      ? JSON.stringify(doc.extracted_data, null, 2)
                      : "暂无结构化数据"}
                  </pre>
                )}
              </div>
            )}

          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}
