import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ExternalLink,
  Copy,
  Download,
  FileText,
  Loader2,
  RotateCcw,
  Save,
} from "lucide-react";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";
import "katex/dist/katex.min.css";

import { ExtractionResultPanel } from "@/components/extraction-result-panel";
import { PdfEvidenceViewer } from "@/components/pdf-evidence-viewer";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useDocument, useDocumentFile, useUpdateDocument } from "@/hooks/use-api";
import {
  buildExtractionItems,
  findFirstPositionedEvidence,
  type ExtractionEvidence,
} from "@/lib/evidence";

interface DocPreviewPanelProps {
  docId: number | null;
  onRawDirtyChange?: (dirty: boolean) => void;
}

/**
 * Coordinate document preview, evidence navigation, Markdown edits, and JSON edits.
 */
export function DocPreviewPanel({
  docId,
  onRawDirtyChange,
}: DocPreviewPanelProps) {
  const { data: doc, isLoading } = useDocument(docId);
  const { data: documentFile, isLoading: isFileLoading } = useDocumentFile(docId);
  const [tab, setTab] = useState("evidence");
  const [resultTab, setResultTab] = useState("items");
  const [rawDraft, setRawDraft] = useState("");
  const [savedRawContent, setSavedRawContent] = useState("");
  const [jsonDraft, setJsonDraft] = useState("");
  const [savedJsonContent, setSavedJsonContent] = useState("");
  const [selectedEvidence, setSelectedEvidence] = useState<ExtractionEvidence | null>(null);
  const [sourcePreview, setSourcePreview] = useState<SourcePreviewState>({
    kind: "empty",
  });
  const updateDocument = useUpdateDocument(docId ?? -1);

  const hasRawChanges = useMemo(
    () => rawDraft !== savedRawContent,
    [rawDraft, savedRawContent],
  );

  const hasJsonChanges = useMemo(
    () => jsonDraft !== savedJsonContent,
    [jsonDraft, savedJsonContent],
  );

  const extractionItems = useMemo(
    () => buildExtractionItems(doc?.extracted_data),
    [doc?.extracted_data],
  );

  useEffect(() => {
    setTab("evidence");
    setResultTab("items");
    setSelectedEvidence(null);
  }, [docId]);

  useEffect(() => {
    setSelectedEvidence((current) => {
      if (current && containsEvidence(extractionItems, current)) {
        return current;
      }
      return findFirstPositionedEvidence(extractionItems);
    });
  }, [extractionItems]);

  useEffect(() => {
    const nextRawContent = doc?.parsed_content ?? "";
    const nextJsonContent = doc?.extracted_data
      ? JSON.stringify(doc.extracted_data, null, 2)
      : "";
    setRawDraft(nextRawContent);
    setSavedRawContent(nextRawContent);
    setJsonDraft(nextJsonContent);
    setSavedJsonContent(nextJsonContent);
  }, [doc?.id, doc?.parsed_content, doc?.extracted_data]);

  useEffect(() => {
    onRawDirtyChange?.(tab === "raw" && hasRawChanges);
  }, [hasRawChanges, onRawDirtyChange, tab]);

  useEffect(() => {
    let objectUrl: string | null = null;
    let disposed = false;

    async function loadPreview() {
      if (!documentFile || !doc) {
        setSourcePreview({ kind: "empty" });
        return;
      }

      const extension = getFileExtension(documentFile.fileName);
      const blob = documentFile.blob;

      if (extension === "pdf" || documentFile.contentType.includes("pdf")) {
        if (!disposed) {
          setSourcePreview({ kind: "pdf" });
        }
        return;
      }

      if (extension === "txt" || extension === "md" || documentFile.contentType.startsWith("text/")) {
        const text = await blob.text();
        if (!disposed) {
          setSourcePreview({ kind: extension === "md" ? "markdown" : "text", text });
        }
        return;
      }

      objectUrl = URL.createObjectURL(blob);
      if (!disposed) {
        setSourcePreview({ kind: "download", url: objectUrl, fileName: documentFile.fileName });
      }
    }

    loadPreview().catch(() => {
      setSourcePreview({ kind: "error" });
    });

    return () => {
      disposed = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [docId, documentFile]);

  const handleCopyJson = async () => {
    if (!jsonDraft) {
      return;
    }
    try {
      await navigator.clipboard.writeText(jsonDraft);
      toast.success("JSON 已复制到剪贴板");
    } catch {
      toast.error("复制失败，请手动复制");
    }
  };

  const handleDownloadJson = () => {
    if (!jsonDraft) {
      return;
    }
    const blob = new Blob([jsonDraft], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `doc-${docId}-extracted-data.json`;
    link.click();
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
      toast.success("Markdown 已保存");
    } catch {
      toast.error("Markdown 保存失败");
    }
  };

  const handleResetJson = () => {
    setJsonDraft(savedJsonContent);
    toast.info("已恢复到最近一次保存的 JSON");
  };

  const handleSaveJson = async () => {
    if (!doc) {
      return;
    }

    let extractedData: Record<string, unknown> | undefined;
    if (jsonDraft.trim()) {
      try {
        extractedData = JSON.parse(jsonDraft) as Record<string, unknown>;
      } catch {
        toast.error("JSON 格式无效，无法保存");
        return;
      }
    }

    try {
      const updatedDoc = await updateDocument.mutateAsync({
        extracted_data: extractedData,
      });
      const nextContent = updatedDoc.extracted_data
        ? JSON.stringify(updatedDoc.extracted_data, null, 2)
        : "";
      setJsonDraft(nextContent);
      setSavedJsonContent(nextContent);
      toast.success("JSON 已保存");
    } catch {
      toast.error("JSON 保存失败");
    }
  };

  if (!docId) {
    return null;
  }

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
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="evidence">证据对照</TabsTrigger>
            <TabsTrigger value="raw">Markdown 校对</TabsTrigger>
          </TabsList>
        </div>

        {doc.error_message && (
          <div className="shrink-0 flex items-center gap-2 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span>{doc.error_message}</span>
          </div>
        )}

        <TabsContent value="evidence" className="m-0 flex-1 overflow-hidden focus-visible:outline-none">
          <div className="flex h-full min-h-0 flex-col bg-background">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
              <div>
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  证据定位
                </p>
                <h3 className="mt-1 text-base font-semibold text-foreground">原始 PDF 与提取结果对照</h3>
              </div>
              <div className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground">
                {extractionItems.length > 0 ? `${extractionItems.length} 个对象` : "暂无对象"}
              </div>
            </div>

            <div className="grid min-h-0 flex-1 gap-4 p-5 xl:grid-cols-[minmax(0,1.08fr)_minmax(360px,0.92fr)]">
              <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border bg-muted/15 shadow-sm">
                <div className="flex items-center justify-between border-b px-4 py-3">
                  <p className="text-xs font-medium tracking-[0.16em] text-muted-foreground uppercase">
                    原始文档 PDF
                  </p>
                  {selectedEvidence?.evidenceId && (
                    <span className="font-mono text-xs text-muted-foreground">
                      {selectedEvidence.evidenceId}
                    </span>
                  )}
                </div>
                <div className="min-h-0 flex-1">
                  <SourcePreview
                    preview={sourcePreview}
                    isLoading={isFileLoading}
                    file={documentFile}
                    selectedEvidence={selectedEvidence}
                  />
                </div>
              </section>

              <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border bg-background shadow-sm">
                <Tabs value={resultTab} onValueChange={setResultTab} className="flex min-h-0 flex-1 flex-col gap-0">
                  <div className="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-3">
                    <div>
                      <p className="text-xs font-medium tracking-[0.16em] text-muted-foreground uppercase">
                        结构化结果
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        点击对象定位对应原文证据
                      </p>
                    </div>
                    <TabsList>
                      <TabsTrigger value="items">提取项</TabsTrigger>
                      <TabsTrigger value="json">JSON</TabsTrigger>
                    </TabsList>
                  </div>

                  <TabsContent value="items" className="m-0 min-h-0 flex-1 overflow-hidden focus-visible:outline-none">
                    <ExtractionResultPanel
                      items={extractionItems}
                      selectedEvidence={selectedEvidence}
                      onSelectEvidence={setSelectedEvidence}
                    />
                  </TabsContent>

                  <TabsContent value="json" className="m-0 min-h-0 flex-1 overflow-hidden focus-visible:outline-none">
                    <div className="flex h-full min-h-0 flex-col">
                      <div className="flex flex-wrap items-center justify-end gap-2 border-b px-4 py-3">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={handleCopyJson}
                          disabled={!jsonDraft}
                        >
                          <Copy data-icon="inline-start" />
                          复制
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={handleDownloadJson}
                          disabled={!jsonDraft}
                        >
                          <Download data-icon="inline-start" />
                          下载
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={handleResetJson}
                          disabled={!hasJsonChanges || updateDocument.isPending}
                        >
                          <RotateCcw data-icon="inline-start" />
                          恢复
                        </Button>
                        <Button
                          size="sm"
                          onClick={handleSaveJson}
                          disabled={!hasJsonChanges || updateDocument.isPending}
                        >
                          {updateDocument.isPending ? (
                            <Loader2 data-icon="inline-start" className="animate-spin" />
                          ) : (
                            <Save data-icon="inline-start" />
                          )}
                          保存 JSON
                        </Button>
                      </div>
                      <div className="min-h-0 flex-1 p-4">
                        <Textarea
                          value={jsonDraft}
                          onChange={(event) => setJsonDraft(event.target.value)}
                          placeholder="这里显示结构化提取结果，可直接修正 JSON。"
                          spellCheck={false}
                          className="h-full min-h-full resize-none border-0 bg-muted/10 font-mono text-sm leading-6 shadow-none"
                        />
                      </div>
                    </div>
                  </TabsContent>
                </Tabs>
              </section>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="raw" className="m-0 flex-1 overflow-hidden focus-visible:outline-none">
          <div className="flex h-full min-h-0 flex-col bg-background">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
              <div>
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Markdown 校对
                </p>
                <h3 className="mt-1 text-base font-semibold text-foreground">解析结果可人工修正</h3>
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
                  <RotateCcw data-icon="inline-start" />
                  恢复
                </Button>
                <Button
                  size="sm"
                  onClick={handleSaveRaw}
                  disabled={!hasRawChanges || updateDocument.isPending}
                >
                  {updateDocument.isPending ? (
                    <Loader2 data-icon="inline-start" className="animate-spin" />
                  ) : (
                    <Save data-icon="inline-start" />
                  )}
                  保存 Markdown
                </Button>
              </div>
            </div>

            <div className="grid min-h-0 flex-1 gap-4 p-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border bg-muted/15 shadow-sm">
                <div className="flex items-center justify-between border-b px-4 py-3">
                  <p className="text-xs font-medium tracking-[0.16em] text-muted-foreground uppercase">
                    原始文档对照
                  </p>
                  {sourcePreview.kind === "download" && sourcePreview.url && (
                    <a
                      href={sourcePreview.url}
                      download={sourcePreview.fileName}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex h-8 items-center justify-center rounded-md border bg-background px-3 text-sm font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                    >
                      <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                      打开原文件
                    </a>
                  )}
                </div>
                <div className="min-h-0 flex-1">
                  <SourcePreview
                    preview={sourcePreview}
                    isLoading={isFileLoading}
                    file={documentFile}
                    selectedEvidence={null}
                  />
                </div>
              </section>
              <section className="flex min-h-0 flex-col rounded-lg border bg-background shadow-sm">
                <div className="border-b px-4 py-3">
                  <p className="text-xs font-medium tracking-[0.16em] text-muted-foreground uppercase">
                    Markdown 编辑
                  </p>
                </div>
                <div className="min-h-0 flex-1 p-4">
                  <Textarea
                    value={rawDraft}
                    onChange={(event) => setRawDraft(event.target.value)}
                    placeholder="这里显示解析后的 Markdown，用户可以直接修正。"
                    spellCheck={false}
                    className="h-full min-h-full resize-none border-0 bg-muted/10 font-mono text-sm leading-6 shadow-none"
                  />
                </div>
              </section>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

type SourcePreviewState =
  | { kind: "empty" }
  | { kind: "pdf" }
  | { kind: "text"; text: string }
  | { kind: "markdown"; text: string }
  | { kind: "download"; url: string; fileName: string }
  | { kind: "error" };

/**
 * Render the best available source preview for the original uploaded file.
 */
function SourcePreview({
  preview,
  isLoading,
  file,
  selectedEvidence,
}: {
  preview: SourcePreviewState;
  isLoading: boolean;
  file: { blob: Blob; contentType: string; fileName: string } | undefined;
  selectedEvidence: ExtractionEvidence | null;
}) {
  if (isLoading) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        加载原文件中...
      </div>
    );
  }

  if (preview.kind === "pdf") {
    return (
      <PdfEvidenceViewer
        file={file}
        isLoading={isLoading}
        selectedEvidence={selectedEvidence}
      />
    );
  }

  if (preview.kind === "text") {
    return (
      <ScrollArea className="h-full">
        <pre className="whitespace-pre-wrap px-5 py-4 font-mono text-sm leading-6 text-foreground">
          {preview.text}
        </pre>
      </ScrollArea>
    );
  }

  if (preview.kind === "markdown") {
    return (
      <ScrollArea className="h-full">
        <div className="prose prose-sm max-w-none px-5 py-4 text-foreground prose-headings:font-semibold prose-pre:bg-muted">
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeKatex, rehypeHighlight]}
          >
            {preview.text}
          </ReactMarkdown>
        </div>
      </ScrollArea>
    );
  }

  if (preview.kind === "download") {
    return (
      <div className="flex h-full min-h-0 flex-col items-center justify-center gap-3 px-6 text-center text-sm text-muted-foreground">
        <FileText className="h-10 w-10 opacity-40" />
        <div>
          <p className="font-medium text-foreground">当前文件类型不支持内嵌预览</p>
          <p className="mt-1">可直接打开原始文件进行对照。</p>
        </div>
      </div>
    );
  }

  if (preview.kind === "error") {
    return (
      <div className="flex h-full min-h-0 items-center justify-center px-6 text-center text-sm text-muted-foreground">
        原始文件加载失败
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 items-center justify-center px-6 text-center text-sm text-muted-foreground">
      暂无原始文件预览
    </div>
  );
}

/**
 * Read a lower-case extension from a file name.
 */
function getFileExtension(fileName: string): string {
  const ext = fileName.split(".").pop();
  return ext ? ext.toLowerCase() : "";
}

/**
 * Check whether the current selected evidence still exists in fresh extraction data.
 */
function containsEvidence(
  items: ReturnType<typeof buildExtractionItems>,
  evidence: ExtractionEvidence,
): boolean {
  return items.some((item) =>
    item.evidence.some((entry) => {
      if (entry.evidenceId && evidence.evidenceId) {
        return entry.evidenceId === evidence.evidenceId;
      }
      return entry.objectId === evidence.objectId && entry.elementId === evidence.elementId;
    }),
  );
}
