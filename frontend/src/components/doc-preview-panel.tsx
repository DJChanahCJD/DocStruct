import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Copy,
  Download,
  ExternalLink,
  FileText,
  Loader2,
  RotateCcw,
  Save,
} from "lucide-react";
import { toast } from "sonner";

import { ReviewModelPanel } from "@/components/review-model-panel";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useDocument, useDocumentSourceMeta, useUpdateDocument } from "@/hooks/use-api";
import type { CitationItem, DocumentSourceMeta } from "@/lib/api";

interface DocPreviewPanelProps {
  docId: number | null;
  mode: "preview" | "citation";
  citationSnippet?: CitationItem | null;
  onRawDirtyChange?: (dirty: boolean) => void;
}

export function DocPreviewPanel({
  docId,
  mode,
  citationSnippet,
  onRawDirtyChange,
}: DocPreviewPanelProps) {
  const { data: doc, isLoading } = useDocument(docId);
  const { data: sourceMeta } = useDocumentSourceMeta(docId);
  const [tab, setTab] = useState("review");
  const [rawDraft, setRawDraft] = useState("");
  const [savedRawContent, setSavedRawContent] = useState("");
  const updateDocument = useUpdateDocument(docId ?? -1);

  const hasRawChanges = useMemo(
    () => rawDraft !== savedRawContent,
    [rawDraft, savedRawContent],
  );

  useEffect(() => {
    setTab("review");
  }, [docId]);

  useEffect(() => {
    const nextContent = doc?.parsed_content ?? "";
    setRawDraft(nextContent);
    setSavedRawContent(nextContent);
  }, [doc?.id, doc?.parsed_content]);

  useEffect(() => {
    onRawDirtyChange?.(tab === "raw" && hasRawChanges);
  }, [hasRawChanges, onRawDirtyChange, tab]);

  /** 复制 JSON 到剪贴板 */
  const handleCopyJson = async () => {
    if (!doc?.extracted_data) return;
    try {
      const jsonString = JSON.stringify(doc.extracted_data, null, 2);
      await navigator.clipboard.writeText(jsonString);
      toast.success("JSON 已复制到剪贴板");
    } catch {
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

  const handleTabChange = (nextTab: string) => {
    if (tab === "raw" && nextTab !== "raw" && hasRawChanges) {
      const confirmed = window.confirm("当前 Markdown 校对内容尚未保存，确定要离开这个标签页吗？");
      if (!confirmed) {
        return;
      }
    }
    setTab(nextTab);
  };

  const handleResetRaw = () => {
    setRawDraft(savedRawContent);
    toast.info("已恢复到最近一次保存的 Markdown");
  };

  const handleSaveRaw = async () => {
    if (!doc) {
      return;
    }
    try {
      const updatedDoc = await updateDocument.mutateAsync({
        parsed_content: rawDraft,
      });
      const nextContent = updatedDoc.parsed_content ?? "";
      setRawDraft(nextContent);
      setSavedRawContent(nextContent);
      if (updatedDoc.error_message) {
        toast.warning(`Markdown 已保存，但索引更新异常：${updatedDoc.error_message}`);
      } else {
        toast.success("Markdown 已保存，并已同步重建索引");
      }
    } catch {
      toast.error("Markdown 保存失败");
    }
  };

  if (!docId) return null;

  if (isLoading) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center bg-background text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span className="mt-3 text-sm tracking-wide">加载中...</span>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-background text-muted-foreground">
        <p className="text-sm">文档不存在</p>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-1 flex-col overflow-hidden bg-background">
      <Tabs value={tab} onValueChange={handleTabChange} className="flex flex-1 flex-col overflow-hidden">
        <div className="shrink-0 border-b px-4 py-2">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="review">审核</TabsTrigger>
            <TabsTrigger value="source">源文件</TabsTrigger>
            <TabsTrigger value="json">JSON</TabsTrigger>
            <TabsTrigger value="raw">原文</TabsTrigger>
          </TabsList>
        </div>

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

        {doc.error_message && (
          <div className="shrink-0 flex items-center gap-2 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span>{doc.error_message}</span>
          </div>
        )}

        <TabsContent value="source" className="m-0 flex-1 overflow-hidden focus-visible:outline-none">
          <ScrollArea className="h-full px-5 py-4">
            <SourcePreview docId={doc.id} sourceMeta={sourceMeta} />
          </ScrollArea>
        </TabsContent>

        <TabsContent value="raw" className="m-0 flex-1 overflow-hidden focus-visible:outline-none">
          <div className="grid h-full min-h-0 gap-0 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
            <div className="min-h-0 border-r bg-muted/10">
              <ScrollArea className="h-full px-5 py-4">
                <SourcePreview docId={doc.id} sourceMeta={sourceMeta} fillHeight />
              </ScrollArea>
            </div>

            <div className="flex min-h-0 flex-col bg-background">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                    Markdown 校对
                  </p>
                  <h3 className="mt-1 text-base font-semibold text-foreground">解析结果可人工修正</h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    保存后会回写正式原文，并同步重建后续检索索引。
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground">
                    {updateDocument.isPending
                      ? "保存中..."
                      : hasRawChanges
                        ? "未保存修改"
                        : "已同步"}
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleResetRaw}
                    disabled={!hasRawChanges || updateDocument.isPending}
                  >
                    <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                    恢复
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSaveRaw}
                    disabled={!hasRawChanges || updateDocument.isPending}
                  >
                    {updateDocument.isPending ? (
                      <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Save className="mr-1.5 h-3.5 w-3.5" />
                    )}
                    保存 Markdown
                  </Button>
                </div>
              </div>

              <div className="grid shrink-0 grid-cols-2 gap-3 border-b px-5 py-3 text-xs text-muted-foreground">
                <div>字符数：{rawDraft.length}</div>
                <div>行数：{rawDraft ? rawDraft.split(/\r?\n/).length : 0}</div>
              </div>

              <div className="min-h-0 flex-1 p-5">
                <Textarea
                  value={rawDraft}
                  onChange={(event) => setRawDraft(event.target.value)}
                  placeholder="这里显示解析后的 Markdown，用户可以直接修正。"
                  spellCheck={false}
                  className="h-full min-h-full resize-none bg-muted/10 font-mono text-sm leading-6"
                />
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="review" className="m-0 flex-1 overflow-hidden focus-visible:outline-none">
          <ScrollArea className="h-full px-5 py-4">
            <ReviewModelPanel docId={doc.id} />
          </ScrollArea>
        </TabsContent>

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

function SourcePreview({
  docId,
  sourceMeta,
  fillHeight = false,
}: {
  docId: number;
  sourceMeta?: DocumentSourceMeta;
  fillHeight?: boolean;
}) {
  if (!sourceMeta) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在加载源文件信息...
      </div>
    );
  }

  const downloadUrl = sourceMeta.download_url;
  const frameClassName = fillHeight
    ? "h-full min-h-[32rem] w-full rounded-md border bg-background"
    : "h-[72vh] w-full rounded-md border bg-background";

  if (sourceMeta.preview_mode === "pdf" || sourceMeta.preview_mode === "text") {
    return (
      <div className={`space-y-3 ${fillHeight ? "flex h-full min-h-0 flex-col" : ""}`}>
        <SourceHeader sourceMeta={sourceMeta} />
        <iframe
          title={`doc-source-${docId}`}
          src={downloadUrl}
          className={frameClassName}
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
            源文件
          </a>
        </Button>
      </div>
    </div>
  );
}
