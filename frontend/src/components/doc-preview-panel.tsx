import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2 } from "lucide-react";
import { useDocument } from "@/hooks/use-api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { CitationItem } from "@/lib/api";

// 类型断言绕过 react-markdown v10 类型定义问题
const Markdown = ReactMarkdown as React.FC<{
  remarkPlugins?: unknown[];
  children?: string;
}>;

interface DocPreviewPanelProps {
  docId: number | null;
  mode: "preview" | "citation";
  citationSnippet?: CitationItem | null;
}

/**
 * 文档预览面板（内联右侧列）
 * 显示选中文档的原文、JSON、错误信息和元数据
 */
export function DocPreviewPanel({
  docId,
  mode,
  citationSnippet,
}: DocPreviewPanelProps) {
  const { data: doc, isLoading } = useDocument(docId);

  if (!docId) return null;

  return (
    <aside className="w-[420px] shrink-0 border-l flex flex-col h-full overflow-hidden bg-background">
      {/* 标题栏 */}
      <header className="border-b px-4 py-3">
        <h2 className="text-sm font-medium truncate">
          {mode === "preview" ? "文档预览" : "引用详情"}:{" "}
          {isLoading ? "加载中..." : doc?.filename ?? `文档 ${docId}`}
        </h2>
      </header>

      {/* 内容区 */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="mt-2 text-sm">加载中...</span>
        </div>
      ) : doc ? (
        <Tabs defaultValue="raw" className="flex flex-col flex-1 overflow-hidden">
          {/* Tab 切换栏 */}
          <div className="px-4 py-2 border-b shrink-0">
            <TabsList className="w-full">
              <TabsTrigger value="raw" className="flex-1">
                原文
              </TabsTrigger>
              <TabsTrigger value="json" className="flex-1">
                JSON
              </TabsTrigger>
              {doc.error_message && (
                <TabsTrigger value="error" className="flex-1">
                  错误
                </TabsTrigger>
              )}
            </TabsList>
          </div>

          {/* 引用片段 - 固定 */}
          {mode === "citation" && citationSnippet && (
            <div className="px-4 py-3 border-b shrink-0">
              <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
                <div className="mb-1 text-xs font-medium uppercase text-primary">
                  引用片段
                </div>
                {citationSnippet.title_path && (
                  <p className="text-xs text-muted-foreground mb-2">
                    {citationSnippet.title_path}
                  </p>
                )}
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {citationSnippet.snippet}
                </p>
              </div>
            </div>
          )}

          {/* 内容区 - 可滚动 */}
          <ScrollArea className="flex-1 h-0 min-h-0 px-4 py-3">
            <TabsContent value="raw" className="mt-0">
              <div className="prose prose-sm dark:prose-invert max-w-none text-sm leading-relaxed">
                <Markdown remarkPlugins={[remarkGfm]}>
                  {doc.parsed_content || "暂无原文内容"}
                </Markdown>
              </div>
            </TabsContent>

            <TabsContent value="json" className="mt-0">
              <pre className="whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs">
                {doc.extracted_data
                  ? JSON.stringify(doc.extracted_data, null, 2)
                  : "暂无结构化数据"}
              </pre>
            </TabsContent>

            {doc.error_message && (
              <TabsContent value="error" className="mt-0">
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {doc.error_message}
                </div>
              </TabsContent>
            )}
          </ScrollArea>

          {/* 元数据 - 固定在底部 */}
          <div className="px-4 py-3 border-t shrink-0 space-y-2 text-sm">
            <DocMetaField label="文件名" value={doc.filename} />
            <DocMetaField label="类型" value={doc.doc_type} />
            <DocMetaField label="来源" value={doc.source_type} />
            {doc.source_url && (
              <DocMetaField label="URL" value={doc.source_url} />
            )}
            <DocMetaField label="状态" value={doc.status} />
          </div>
        </Tabs>
      ) : (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <p className="text-sm">文档不存在</p>
        </div>
      )}
    </aside>
  );
}

function DocMetaField({
  label,
  value,
}: {
  label: string;
  value: string | null;
}) {
  return (
    <div className="flex justify-between border-b py-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium truncate ml-2">{value ?? "-"}</span>
    </div>
  );
}
