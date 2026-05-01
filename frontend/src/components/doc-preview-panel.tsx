import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ExternalLink,
  Copy,
  Download,
  FileEdit,
  FileText,
  Loader2,
  RotateCcw,
  Save,
  Braces,
  SlidersHorizontal,
} from "lucide-react";
import { toast } from "sonner";
import "highlight.js/styles/github-dark.css";
import "katex/dist/katex.min.css";

import { ExtractionMetadataDialog } from "@/components/extraction-metadata-dialog";
import { ExtractionResultPanel } from "@/components/extraction-result-panel";
import { DocxEvidenceViewer } from "@/components/docx-evidence-viewer";
import { JsonCodeEditor } from "@/components/json-code-editor";
import { MarkdownEvidenceViewer } from "@/components/markdown-evidence-viewer";
import { PdfEvidenceViewer } from "@/components/pdf-evidence-viewer";
import { PlainTextEvidenceViewer } from "@/components/plain-text-evidence-viewer";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { useDocument, useDocumentFile, useUpdateDocument } from "@/hooks/use-api";
import type { DocumentIR } from "@/lib/api";
import {
  buildExtractionItems,
  findFirstPositionedEvidence,
  type ExtractionEvidence,
  type ExtractionItem,
} from "@/lib/evidence";
import { formatMetadataSummary } from "@/lib/metadata";

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
  const [rawSheetOpen, setRawSheetOpen] = useState(false);
  const [, setChunkSheetOpen] = useState(false);
  const [rawDraft, setRawDraft] = useState("");
  const [savedRawContent, setSavedRawContent] = useState("");
  const [jsonDraft, setJsonDraft] = useState("");
  const [savedJsonContent, setSavedJsonContent] = useState("");
  const [selectedEvidence, setSelectedEvidence] = useState<ExtractionEvidence | null>(null);
  const [selectedItem, setSelectedItem] = useState<ExtractionItem | null>(null);
  const [metadataDialogOpen, setMetadataDialogOpen] = useState(false);
  const [jsonSheetOpen, setJsonSheetOpen] = useState(false);
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
    () => buildExtractionItems(doc?.extracted_data, doc?.doc_type),
    [doc?.extracted_data, doc?.doc_type],
  );
  const documentIr = useMemo(
    () => normalizeDocumentIr(doc?.document_ir),
    [doc?.document_ir],
  );

  const metadataTitle = useMemo(
    () => formatMetadataSummary(doc?.doc_type, doc?.extracted_data),
    [doc],
  );

  useEffect(() => {
    setSelectedEvidence(null);
    setSelectedItem(null);
    setMetadataDialogOpen(false);
    setJsonSheetOpen(false);
    setRawSheetOpen(false);
    setChunkSheetOpen(false);
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
    const nextRawContent = doc?.raw_text ?? "";
    const nextJsonContent = doc?.extracted_data
      ? JSON.stringify(doc.extracted_data, null, 2)
      : "";
    setRawDraft(nextRawContent);
    setSavedRawContent(nextRawContent);
    setJsonDraft(nextJsonContent);
    setSavedJsonContent(nextJsonContent);
  }, [doc?.id, doc?.raw_text, doc?.extracted_data]);

  useEffect(() => {
    onRawDirtyChange?.(rawSheetOpen && hasRawChanges);
  }, [hasRawChanges, onRawDirtyChange, rawSheetOpen]);

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

      if (
        extension === "docx" ||
        extension === "doc" ||
        documentFile.contentType.includes("wordprocessingml")
      ) {
        if (!disposed) {
          setSourcePreview({ kind: "docx" });
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
        raw_text: rawDraft,
      });
      const nextContent = updatedDoc.raw_text ?? "";
      setRawDraft(nextContent);
      setSavedRawContent(nextContent);
      toast.success("Markdown 已保存");
    } catch {
      toast.error("Markdown 保存失败");
    }
  };

  const handleRawSheetOpenChange = (open: boolean) => {
    if (!open && hasRawChanges) {
      const confirmed = window.confirm("当前 Markdown 校对内容尚未保存，确定要关闭吗？");
      if (!confirmed) {
        return;
      }
    }
    setRawSheetOpen(open);
  };

  const handleOpenJsonSheet = (item?: ExtractionItem) => {
    if (item) setSelectedItem(item);
    setRawSheetOpen(false);
    setJsonSheetOpen(true);
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
    let formattedJson = "";

    if (jsonDraft.trim()) {
      try {
        extractedData = JSON.parse(jsonDraft) as Record<string, unknown>;
        formattedJson = JSON.stringify(extractedData, null, 2);
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
        : formattedJson;

      setJsonDraft(nextContent);
      setSavedJsonContent(nextContent);
      toast.success("JSON 已保存");
    } catch {
      toast.error("JSON 保存失败");
    }
  };

  const handleFormatJson = () => {
    try {
      const parsed = JSON.parse(jsonDraft);
      setJsonDraft(JSON.stringify(parsed, null, 2));
      toast.success("JSON 已格式化");
    } catch {
      toast.error("JSON 格式无效，无法格式化");
    }
  };

  const handlePatchExtractionItem = async (
    item: ExtractionItem,
    patch: Record<string, unknown>,
  ) => {
    if (!doc?.extracted_data) {
      return;
    }

    const updatedData = patchExtractionItem(doc.extracted_data, item, patch);
    try {
      const updatedDoc = await updateDocument.mutateAsync({
        extracted_data: updatedData,
      });
      const nextContent = updatedDoc.extracted_data
        ? JSON.stringify(updatedDoc.extracted_data, null, 2)
        : "";
      setJsonDraft(nextContent);
      setSavedJsonContent(nextContent);
      toast.success("提取项已保存");
    } catch {
      toast.error("提取项保存失败");
    }
  };

  const handlePatchMetadata = async (patch: Record<string, unknown>) => {
    if (!doc?.extracted_data) {
      return;
    }

    const updatedData = {
      ...doc.extracted_data,
      ...patch,
    };
    try {
      const updatedDoc = await updateDocument.mutateAsync({
        extracted_data: updatedData,
      });
      const nextContent = updatedDoc.extracted_data
        ? JSON.stringify(updatedDoc.extracted_data, null, 2)
        : "";
      setJsonDraft(nextContent);
      setSavedJsonContent(nextContent);
      toast.success("文档元数据已保存");
    } catch {
      toast.error("文档元数据保存失败");
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
      {doc.error_message && (
        <div className="shrink-0 flex items-center gap-2 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          <span>{doc.error_message}</span>
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col bg-background">
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
            <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
              <p className="min-w-0 truncate text-sm font-medium text-foreground">
                {documentFile?.fileName ?? "原始文档"}
              </p>
              <div className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                {selectedEvidence?.page && <span>Page {selectedEvidence.page}</span>}
                {selectedEvidence?.elementId && (
                  <span className="max-w-40 truncate font-mono">
                    {selectedEvidence.elementId}
                  </span>
                )}
              </div>
            </div>
            <div className="min-h-0 flex-1">
              <SourcePreview
                preview={sourcePreview}
                isLoading={isFileLoading}
                file={documentFile}
                documentIr={documentIr}
                items={extractionItems}
                selectedEvidence={selectedEvidence}
                onSelectEvidence={setSelectedEvidence}
              />
            </div>
          </section>

          <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border bg-background shadow-sm">
            <div className="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-3">
              <div>
                <p className="text-xs font-medium tracking-[0.16em] text-muted-foreground uppercase">
                  结构化结果
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  点击对象定位原文证据，必要时打开 JSON 校正
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setMetadataDialogOpen(true)}
                  disabled={!doc.extracted_data}
                  title={metadataTitle}
                >
                  <SlidersHorizontal data-icon="inline-start" />
                  元数据
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handleOpenJsonSheet()}
                  disabled={!jsonDraft}
                >
                  <Braces data-icon="inline-start" />
                  JSON
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setRawSheetOpen(true)}
                  disabled={!rawDraft}
                >
                  <FileEdit data-icon="inline-start" />
                  Markdown
                </Button>
              </div>
            </div>
            <div className="min-h-0 flex-1">
              <ExtractionResultPanel
                items={extractionItems}
                selectedEvidence={selectedEvidence}
                onSelectEvidence={setSelectedEvidence}
                onPatchItem={handlePatchExtractionItem}
                onSelectedItemChange={setSelectedItem}
                onEditItem={handleOpenJsonSheet}
              />
            </div>
          </section>
        </div>
      </div>

      <ExtractionMetadataDialog
        open={metadataDialogOpen}
        onOpenChange={setMetadataDialogOpen}
        docType={doc.doc_type}
        extractedData={doc.extracted_data}
        isSaving={updateDocument.isPending}
        onSave={handlePatchMetadata}
      />
      <Sheet open={jsonSheetOpen} onOpenChange={setJsonSheetOpen}>
        <SheetContent
          className="gap-0 p-0 sm:max-w-none"
          style={{ width: "min(1200px, 90vw)", maxWidth: "none" }}
        >
          <SheetHeader className="border-b pr-12">
            <SheetTitle>结构化 JSON</SheetTitle>
            <SheetDescription>
              {selectedItem?.slotLabel && selectedItem?.title
                ? `已定位到 ${selectedItem.slotLabel}：${selectedItem.title}`
                : "可直接校正整份结构化结果"}
            </SheetDescription>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3">
              <div className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground">
                {updateDocument.isPending ? "保存中..." : hasJsonChanges ? "未保存修改" : "已同步"}
              </div>
              <div className="flex flex-wrap items-center gap-2">
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
                  variant="secondary"
                  size="sm"
                  onClick={handleFormatJson}
                  disabled={!jsonDraft || updateDocument.isPending}
                >
                  格式化
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
            </div>
            <div className="min-h-0 flex-1 p-4">
              <JsonCodeEditor
                value={jsonDraft}
                onChange={setJsonDraft}
                selectedItem={selectedItem}
              />
            </div>
          </div>
        </SheetContent>
      </Sheet>
      <Sheet open={rawSheetOpen} onOpenChange={handleRawSheetOpenChange}>
        <SheetContent
          className="gap-0 p-0 sm:max-w-none"
          style={{ width: "min(1200px, 90vw)", maxWidth: "none" }}
        >
          <SheetHeader className="border-b pr-12">
            <SheetTitle>Markdown 校对</SheetTitle>
            <SheetDescription>解析结果可人工修正</SheetDescription>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
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
                    documentIr={documentIr}
                    items={[]}
                    selectedEvidence={null}
                    onSelectEvidence={() => undefined}
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
        </SheetContent>
      </Sheet>
    </div>
  );
}

type SourcePreviewState =
  | { kind: "empty" }
  | { kind: "pdf" }
  | { kind: "docx" }
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
  documentIr,
  items,
  selectedEvidence,
  onSelectEvidence,
}: {
  preview: SourcePreviewState;
  isLoading: boolean;
  file: { blob: Blob; contentType: string; fileName: string } | undefined;
  documentIr: DocumentIR | null;
  items: ExtractionItem[];
  selectedEvidence: ExtractionEvidence | null;
  onSelectEvidence: (evidence: ExtractionEvidence) => void;
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
        items={items}
        selectedEvidence={selectedEvidence}
        onSelectEvidence={onSelectEvidence}
      />
    );
  }

  if (preview.kind === "docx") {
    return (
      <DocxEvidenceViewer
        documentIr={documentIr}
        items={items}
        selectedEvidence={selectedEvidence}
        onSelectEvidence={onSelectEvidence}
      />
    );
  }

  if (preview.kind === "markdown") {
    return (
      <MarkdownEvidenceViewer
        markdown={preview.text}
        items={items}
        selectedEvidence={selectedEvidence}
        onSelectEvidence={onSelectEvidence}
      />
    );
  }

  if (preview.kind === "text") {
    return (
      <PlainTextEvidenceViewer
        text={preview.text}
        items={items}
        selectedEvidence={selectedEvidence}
        onSelectEvidence={onSelectEvidence}
      />
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
      if (entry.elementId || evidence.elementId) {
        return entry.objectId === evidence.objectId && entry.elementId === evidence.elementId;
      }
      return entry.objectId === evidence.objectId && entry.textSpan === evidence.textSpan && entry.page === evidence.page;
    }),
  );
}

/**
 * Patch one extracted object inside the structured JSON payload.
 */
function patchExtractionItem(
  extractedData: Record<string, unknown>,
  item: ExtractionItem,
  patch: Record<string, unknown>,
): Record<string, unknown> {
  const slotItems = extractedData[item.slot];
  if (!Array.isArray(slotItems)) {
    return extractedData;
  }

  return {
    ...extractedData,
    [item.slot]: slotItems.map((slotItem) => {
      if (!isRecord(slotItem) || slotItem.id !== item.id) {
        return slotItem;
      }
      return {
        ...slotItem,
        ...patch,
      };
    }),
  };
}

/**
 * Return true when a value is a JSON-like object.
 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Narrow the API document_ir payload into the frontend DocumentIR shape.
 */
function normalizeDocumentIr(value: Record<string, unknown> | null | undefined): DocumentIR | null {
  if (!isRecord(value) || !Array.isArray(value.elements)) {
    return null;
  }
  return value as unknown as DocumentIR;
}
