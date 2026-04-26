import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, FileSearch, Loader2, RotateCcw } from "lucide-react";
import * as pdfjsLib from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.mjs?url";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { DocumentFilePayload } from "@/lib/api";
import type { ExtractionEvidence } from "@/lib/evidence";
import { cn } from "@/lib/utils";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

interface PdfEvidenceViewerProps {
  file: DocumentFilePayload | undefined;
  isLoading: boolean;
  selectedEvidence: ExtractionEvidence | null;
}

interface PdfDocument {
  numPages: number;
  getPage: (pageNumber: number) => Promise<PdfPage>;
  destroy: () => Promise<void>;
}

interface PdfPage {
  getViewport: (options: { scale: number }) => PdfViewport;
  render: (params: {
    canvasContext: CanvasRenderingContext2D;
    canvas: HTMLCanvasElement;
    viewport: PdfViewport;
  }) => PdfRenderTask;
}

interface PdfViewport {
  width: number;
  height: number;
  convertToViewportRectangle: (rect: number[]) => number[];
}

interface PdfRenderTask {
  promise: Promise<void>;
  cancel: () => void;
}

interface HighlightRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/**
 * Render the source PDF and highlight the selected Docling evidence bbox.
 */
export function PdfEvidenceViewer({
  file,
  isLoading,
  selectedEvidence,
}: PdfEvidenceViewerProps) {
  const [pdf, setPdf] = useState<PdfDocument | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activePage, setActivePage] = useState(1);
  const pageRefs = useRef(new Map<number, HTMLDivElement>());

  useEffect(() => {
    let disposed = false;
    let activePdf: PdfDocument | null = null;
    const loadingTaskRef: { current: { destroy: () => void | Promise<void> } | null } = {
      current: null,
    };

    async function loadPdf() {
      if (!file) {
        setPdf(null);
        setLoadError(null);
        return;
      }

      setLoadError(null);
      setPdf(null);
      const data = new Uint8Array(await file.blob.arrayBuffer());
      const loadingTask = pdfjsLib.getDocument({ data });
      loadingTaskRef.current = loadingTask;
      const loadedPdf = (await loadingTask.promise) as unknown as PdfDocument;
      activePdf = loadedPdf;
      if (!disposed) {
        setPdf(loadedPdf);
      }
    }

    loadPdf().catch(() => {
      if (!disposed) {
        setLoadError("PDF 加载失败");
        setPdf(null);
      }
    });

    return () => {
      disposed = true;
      void loadingTaskRef.current?.destroy();
      void activePdf?.destroy();
    };
  }, [file]);

  useEffect(() => {
    const pageNumber = selectedEvidence?.page;
    if (!pageNumber) {
      return;
    }

    setActivePage(pageNumber);
    window.setTimeout(() => {
      const target = pageRefs.current.get(pageNumber);
      if (target) {
        target.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    }, 0);
  }, [pdf, selectedEvidence]);

  const pageNumbers = useMemo(() => {
    if (!pdf) {
      return [];
    }
    return Array.from({ length: pdf.numPages }, (_item, index) => index + 1);
  }, [pdf]);

  const registerPageRef = useCallback((pageNumber: number, node: HTMLDivElement | null) => {
    if (node) {
      pageRefs.current.set(pageNumber, node);
      return;
    }
    pageRefs.current.delete(pageNumber);
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center text-sm text-muted-foreground">
        <Loader2 data-icon="inline-start" className="animate-spin" />
        加载原文件中...
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex h-full min-h-0 flex-col items-center justify-center gap-3 px-6 text-center text-sm text-muted-foreground">
        <AlertCircle className="opacity-50" />
        <span>{loadError}</span>
      </div>
    );
  }

  if (!pdf) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center px-6 text-center text-sm text-muted-foreground">
        暂无 PDF 预览
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-muted/20">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b bg-background px-4 py-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-foreground">{file?.fileName}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">{pdf.numPages} 页</div>
        </div>
        {selectedEvidence?.page ? (
          <Badge variant="secondary" className="shrink-0">
            Page {selectedEvidence.page}
          </Badge>
        ) : (
          <Badge variant="outline" className="shrink-0">
            无定位
          </Badge>
        )}
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-5 py-5">
          {pageNumbers.map((pageNumber) => (
            <PdfPageView
              key={pageNumber}
              pdf={pdf}
              pageNumber={pageNumber}
              evidence={selectedEvidence?.page === pageNumber ? selectedEvidence : null}
              active={selectedEvidence?.page === pageNumber}
              shouldRender={Math.abs(pageNumber - activePage) <= 1}
              refCallback={registerPageRef}
            />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}

interface PdfPageViewProps {
  pdf: PdfDocument;
  pageNumber: number;
  evidence: ExtractionEvidence | null;
  active: boolean;
  shouldRender: boolean;
  refCallback: (pageNumber: number, node: HTMLDivElement | null) => void;
}

/**
 * Render one PDF page canvas and its evidence overlay.
 */
function PdfPageView({
  pdf,
  pageNumber,
  evidence,
  active,
  shouldRender,
  refCallback,
}: PdfPageViewProps) {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const viewportRef = useRef<PdfViewport | null>(null);
  const evidenceRef = useRef<ExtractionEvidence | null>(evidence);
  const [frameWidth, setFrameWidth] = useState(0);
  const [pageSize, setPageSize] = useState({ width: 0, height: 0 });
  const [highlightRect, setHighlightRect] = useState<HighlightRect | null>(null);
  const [renderError, setRenderError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const node = frameRef.current;
    if (!node) {
      return;
    }
    refCallback(pageNumber, node);
    return () => refCallback(pageNumber, null);
  }, [pageNumber, refCallback]);

  useEffect(() => {
    const node = frameRef.current;
    if (!node) {
      return;
    }
    const resizeObserver = new ResizeObserver((entries) => {
      const nextWidth = entries[0]?.contentRect.width ?? 0;
      setFrameWidth(nextWidth);
    });
    resizeObserver.observe(node);
    setFrameWidth(node.clientWidth);
    return () => resizeObserver.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    let renderTask: PdfRenderTask | null = null;

    async function renderPage() {
      if (!shouldRender) {
        return;
      }
      const page = await pdf.getPage(pageNumber);
      const baseViewport = page.getViewport({ scale: 1 });
      const availableWidth = Math.max(frameWidth - 32, 320);
      const scale = Math.min(1.55, Math.max(0.72, availableWidth / baseViewport.width));
      const viewport = page.getViewport({ scale });
      const canvas = canvasRef.current;
      const context = canvas?.getContext("2d");

      if (!canvas || !context) {
        return;
      }

      const outputScale = window.devicePixelRatio || 1;
      canvas.width = Math.floor(viewport.width * outputScale);
      canvas.height = Math.floor(viewport.height * outputScale);
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      context.setTransform(outputScale, 0, 0, outputScale, 0, 0);
      context.clearRect(0, 0, viewport.width, viewport.height);

      renderTask = page.render({ canvasContext: context, canvas, viewport });
      await renderTask.promise;

      if (!cancelled) {
        viewportRef.current = viewport;
        setPageSize({ width: viewport.width, height: viewport.height });
        setHighlightRect(calculateHighlightRect(evidenceRef.current, viewport));
        setRenderError(false);
      }
    }

    renderPage().catch((error: unknown) => {
      if (!cancelled && !isRenderCancelled(error)) {
        setRenderError(true);
      }
    });

    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [frameWidth, pageNumber, pdf, retryKey, shouldRender]);

  useEffect(() => {
    evidenceRef.current = evidence;
    setHighlightRect(calculateHighlightRect(evidence, viewportRef.current));
  }, [evidence]);

  return (
    <div ref={frameRef} className="flex w-full justify-center">
      <div
        className={cn(
          "relative rounded-lg border bg-background p-3 shadow-sm transition-colors",
          active ? "border-primary ring-2 ring-primary/20" : "border-border",
        )}
      >
        <div className="mb-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
          <span>Page {pageNumber}</span>
          {evidence?.evidenceId && <span className="font-mono">{evidence.evidenceId}</span>}
        </div>
        <div
          className="relative overflow-hidden rounded-md bg-white"
          style={{
            width: pageSize.width ? `${pageSize.width}px` : undefined,
            height: pageSize.height ? `${pageSize.height}px` : undefined,
            minWidth: pageSize.width ? undefined : "320px",
            minHeight: pageSize.height ? undefined : "420px",
          }}
        >
          {shouldRender ? (
            <canvas ref={canvasRef} className="block" />
          ) : (
            <div className="flex h-[420px] w-[320px] items-center justify-center text-xs text-muted-foreground">
              Page {pageNumber}
            </div>
          )}
          {highlightRect && (
            <div
              className="pointer-events-none absolute rounded-sm border-2 border-primary bg-primary/20 shadow-[0_0_0_9999px_rgba(0,0,0,0.08)]"
              style={{
                left: `${highlightRect.left}px`,
                top: `${highlightRect.top}px`,
                width: `${highlightRect.width}px`,
                height: `${highlightRect.height}px`,
              }}
            >
              <div className="absolute -top-6 left-0 rounded-md bg-primary px-2 py-0.5 text-[11px] font-medium text-primary-foreground">
                证据
              </div>
            </div>
          )}
          {renderError && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-background/90 text-sm text-muted-foreground">
              <FileSearch />
              <span>页面渲染失败</span>
              <Button variant="secondary" size="sm" onClick={() => setRetryKey((value) => value + 1)}>
                <RotateCcw data-icon="inline-start" />
                重试
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Convert a backend PDF bbox into viewport overlay coordinates.
 */
function calculateHighlightRect(
  evidence: ExtractionEvidence | null,
  viewport: PdfViewport | null,
): HighlightRect | null {
  if (!evidence?.bbox || !viewport) {
    return null;
  }

  const [x1, y1, x2, y2] = viewport.convertToViewportRectangle(evidence.bbox);
  const left = Math.min(x1, x2);
  const top = Math.min(y1, y2);
  const width = Math.abs(x2 - x1);
  const height = Math.abs(y2 - y1);

  if (width <= 0 || height <= 0) {
    return null;
  }

  return { left, top, width, height };
}

/**
 * Detect PDF.js render cancellation errors from page rerenders.
 */
function isRenderCancelled(error: unknown): boolean {
  return isErrorWithName(error) && error.name === "RenderingCancelledException";
}

/**
 * Narrow unknown errors that expose a name field.
 */
function isErrorWithName(error: unknown): error is { name: string } {
  return typeof error === "object" && error !== null && "name" in error;
}
