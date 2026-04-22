import { useState, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Loader2, AlertCircle, Copy, Download, ExternalLink, FileText } from "lucide-react";
import { useDocument, useDocumentSourceMeta } from "@/hooks/use-api";
import { ReviewModelPanel } from "@/components/review-model-panel";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import type { CitationItem, DocumentSourceMeta } from "@/lib/api";

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
  const { data: sourceMeta } = useDocumentSourceMeta(docId);
  const [tab, setTab] = useState("review");

  useEffect(() => {
    setTab("review");
  }, [docId]);

  /** 复制 JSON 到剪贴板 */
  const handleCopyJson = async () => {
    if (!doc?.extracted_data) return;
    try {
      const jsonString = JSON.stringify(doc.extracted_data, null, 2);
      await navigator.clipboard.writeText(jsonString);
      toast.success("JSON 已复制到剪贴板");
    } catch (error) {
      toast.error("复制失败，请手动复制");
    }
  };

  /** 下载 JSON 文件 */
  const handleDownloadJson = () => {
    if (!doc?.extracted_data) return;
    const jsonString = JSON.stringify(doc.extracted_data, null, 2);
    const blob = new Blob([jsonString], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `doc-${doc.id}-extracted-data.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("JSON 已下载");
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
      <Tabs value={tab} onValueChange={setTab} className="flex flex-1 flex-col overflow-hidden">

        {/* 顶部 Tab 导航 */}
        <div className="shrink-0 border-b px-4 py-2">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="review">审核</TabsTrigger>
            <TabsTrigger value="source">源文件</TabsTrigger>
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

        <TabsContent value="source" className="m-0 flex-1 overflow-hidden focus-visible:outline-none">
          <ScrollArea className="h-full px-5 py-4">
            <SourcePreview docId={doc.id} sourceMeta={sourceMeta} />
          </ScrollArea>
        </TabsContent>

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

        <TabsContent value="review" className="m-0 flex-1 overflow-hidden focus-visible:outline-none">
          <ScrollArea className="h-full px-5 py-4">
            <ReviewModelPanel docId={doc.id} />
          </ScrollArea>
        </TabsContent>

        {/* JSON 视图 */}
        <TabsContent value="json" className="m-0 flex-1 overflow-hidden focus-visible:outline-none">
          <ScrollArea className="h-full px-5 py-4">
            <div className="space-y-3">
              <div className="flex justify-end gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  className="h-8"
                  onClick={handleCopyJson}
                  disabled={!doc.extracted_data}
                >
                  <Copy className="mr-1.5 h-3.5 w-3.5" />
                  复制 JSON
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  className="h-8"
                  onClick={handleDownloadJson}
                  disabled={!doc.extracted_data}
                >
                  <Download className="mr-1.5 h-3.5 w-3.5" />
                  下载 JSON
                </Button>
              </div>
              <pre className="overflow-x-auto whitespace-pre-wrap rounded-md bg-muted/50 p-4 font-mono text-sm leading-relaxed">
                {doc.extracted_data
                  ? JSON.stringify(doc.extracted_data, null, 2)
                  : "暂无结构化数据"}
              </pre>
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function SourcePreview({ docId, sourceMeta }: { docId: number; sourceMeta?: DocumentSourceMeta }) {
  if (!sourceMeta) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在加载源文件信息...
      </div>
    );
  }

  const downloadUrl = sourceMeta.download_url;

  if (sourceMeta.preview_mode === "pdf") {
    return (
      <div className="space-y-3">
        <SourceHeader sourceMeta={sourceMeta} />
        <iframe
          title={`doc-source-${docId}`}
          src={downloadUrl}
          className="h-[72vh] w-full rounded-md border bg-background"
        />
      </div>
    );
  }

  if (sourceMeta.preview_mode === "text") {
    return (
      <div className="space-y-3">
        <SourceHeader sourceMeta={sourceMeta} />
        <iframe
          title={`doc-source-${docId}`}
          src={downloadUrl}
          className="h-[72vh] w-full rounded-md border bg-background"
        />
      </div>
    );
  }

  if (sourceMeta.preview_mode === "external_url") {
    return (
      <div className="rounded-md border bg-muted/20 p-4">
        <SourceHeader sourceMeta={sourceMeta} />
        <p className="mt-3 text-sm text-muted-foreground">
          该文档来源于外部网页，系统保留原始地址，不做本地文件预览。
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-md border bg-muted/20 p-4">
      <SourceHeader sourceMeta={sourceMeta} />
      <p className="mt-3 text-sm text-muted-foreground">
        当前类型暂不支持浏览器内高保真预览，可直接下载查看源文件。
      </p>
    </div>
  );
}

function SourceHeader({ sourceMeta }: { sourceMeta: DocumentSourceMeta }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-background p-3">
      <div>
        <div className="flex items-center gap-2 text-sm font-medium">
          <FileText className="h-4 w-4" />
          <span>{sourceMeta.filename}</span>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {sourceMeta.mime_type} · {sourceMeta.source_type}
        </p>
      </div>
      <div className="flex gap-2">
        {sourceMeta.source_url && (
          <Button size="sm" variant="secondary" className="h-8">
            <a href={sourceMeta.source_url} target="_blank" rel="noreferrer">
              <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
              打开来源
            </a>
          </Button>
        )}
        <Button size="sm" variant="secondary" className="h-8">
          <a href={sourceMeta.download_url} target="_blank" rel="noreferrer">
            <Download className="mr-1.5 h-3.5 w-3.5" />
            打开源文件
          </a>
        </Button>
      </div>
    </div>
  );
}
