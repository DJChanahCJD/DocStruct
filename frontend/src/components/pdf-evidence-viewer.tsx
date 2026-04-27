import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, FileSearch, Loader2, RotateCcw } from "lucide-react";
import * as pdfjsLib from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.mjs?url";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { DocumentFilePayload } from "@/lib/api";
import {
  evidenceMatches,
  type ExtractionEvidence,
  type ExtractionItem,
} from "@/lib/evidence";
import { cn } from "@/lib/utils";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

interface PdfEvidenceViewerProps {
  file: DocumentFilePayload | undefined;
  isLoading: boolean;
  items: ExtractionItem[];
  selectedEvidence: ExtractionEvidence | null;
  onSelectEvidence: (evidence: ExtractionEvidence) => void;
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

interface EvidenceOverlay {
  evidence: ExtractionEvidence;
  label: string;
  slotLabel: string;
}

interface EvidenceOverlayCluster {
  rect: HighlightRect;
  overlays: EvidenceOverlay[];
}

/**
 * Render the source PDF and highlight the selected Docling evidence bbox.
 */
export function PdfEvidenceViewer({
  file,
  isLoading,
  items,
  selectedEvidence,
  onSelectEvidence,
}: PdfEvidenceViewerProps) {
  const [pdf, setPdf] = useState<PdfDocument | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
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

    window.setTimeout(() => {
      const target = pageRefs.current.get(pageNumber);
      if (target) {
        target.scrollIntoView({ block: "center", behavior: "smooth" });
        // scrollPageIntoReadingPosition(target);
      }
    }, 0);
  }, [pdf, selectedEvidence]);

  const pageNumbers = useMemo(() => {
    if (!pdf) {
      return [];
    }
    return Array.from({ length: pdf.numPages }, (_item, index) => index + 1);
  }, [pdf]);

  const overlaysByPage = useMemo(() => buildOverlaysByPage(items), [items]);

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
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-5 py-5">
          {pageNumbers.map((pageNumber) => (
            <PdfPageView
              key={pageNumber}
              pdf={pdf}
              pageNumber={pageNumber}
              overlays={overlaysByPage.get(pageNumber) ?? []}
              selectedEvidence={selectedEvidence}
              active={selectedEvidence?.page === pageNumber}
              onSelectEvidence={onSelectEvidence}
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
  overlays: EvidenceOverlay[];
  selectedEvidence: ExtractionEvidence | null;
  active: boolean;
  onSelectEvidence: (evidence: ExtractionEvidence) => void;
  refCallback: (pageNumber: number, node: HTMLDivElement | null) => void;
}

/**
 * Render one PDF page canvas and its evidence overlay.
 */
function PdfPageView({
  pdf,
  pageNumber,
  overlays,
  selectedEvidence,
  active,
  onSelectEvidence,
  refCallback,
}: PdfPageViewProps) {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const viewportRef = useRef<PdfViewport | null>(null);
  const overlaysRef = useRef<EvidenceOverlay[]>(overlays);
  const [frameWidth, setFrameWidth] = useState(0);
  const [pageSize, setPageSize] = useState({ width: 0, height: 0 });
  const [highlightClusters, setHighlightClusters] = useState<EvidenceOverlayCluster[]>([]);
  const [isRenderReady, setIsRenderReady] = useState(false);
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
    const node = frameRef.current;
    if (!node) {
      return;
    }

    if (!("IntersectionObserver" in window)) {
      setIsRenderReady(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) {
          return;
        }
        setIsRenderReady(true);
        observer.disconnect();
      },
      {
        root: findScrollAreaViewport(node),
        rootMargin: "600px 0px",
      },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    let renderTask: PdfRenderTask | null = null;

    async function renderPage() {
      if (!isRenderReady) {
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
        setHighlightClusters(calculateOverlayClusters(overlaysRef.current, viewport));
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
  }, [frameWidth, isRenderReady, pageNumber, pdf, retryKey]);

  useEffect(() => {
    overlaysRef.current = overlays;
    setHighlightClusters(calculateOverlayClusters(overlays, viewportRef.current));
  }, [overlays]);

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
          {overlays.length > 0 && <span>{overlays.length} 条证据</span>}
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
          {isRenderReady ? (
            <canvas ref={canvasRef} className="block" />
          ) : (
            <div className="flex h-[420px] w-[320px] items-center justify-center text-xs text-muted-foreground">
              Page {pageNumber}
            </div>
          )}
          {highlightClusters.map((cluster, index) => {
            const primaryOverlay = cluster.overlays[0];
            const isSelected = cluster.overlays.some((overlay) => evidenceMatches(overlay.evidence, selectedEvidence));
            const clusterTitle = cluster.overlays
              .map((overlay) => `${overlay.slotLabel}: ${overlay.label}`)
              .join("\n");
            const buttonClassName = cn(
              "absolute rounded-sm border text-left transition-colors",
              isSelected
                ? "z-20 border-primary bg-primary/10 ring-2 ring-primary/45"
                : "z-10 border-amber-500/80 bg-amber-300/10 hover:bg-amber-300/18",
            );
            const buttonStyle = {
              left: `${cluster.rect.left}px`,
              top: `${cluster.rect.top}px`,
              width: `${cluster.rect.width}px`,
              height: `${cluster.rect.height}px`,
            };

            if (cluster.overlays.length > 1) {
              return (
                <DropdownMenu key={`${pageNumber}-${cluster.rect.left}-${cluster.rect.top}-${index}`}>
                  <DropdownMenuTrigger
                    title={clusterTitle}
                    className={buttonClassName}
                    style={buttonStyle}
                  />
                  <DropdownMenuContent className="w-64">
                    {cluster.overlays.map((overlay, overlayIndex) => (
                      <DropdownMenuItem
                        key={`${overlay.evidence.objectId}-${overlay.evidence.elementId ?? overlay.evidence.textSpan ?? overlayIndex}`}
                        onClick={() => onSelectEvidence(overlay.evidence)}
                        className="flex-col items-start gap-0.5"
                      >
                        <span className="max-w-full truncate text-sm font-medium">{overlay.label}</span>
                        <span className="max-w-full truncate font-mono text-[11px] text-muted-foreground">
                          {overlay.slotLabel} / {overlay.evidence.objectId}
                        </span>
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              );
            }

            return primaryOverlay ? (
              <button
                key={`${primaryOverlay.evidence.objectId}-${primaryOverlay.evidence.elementId ?? primaryOverlay.evidence.textSpan ?? index}`}
                type="button"
                title={clusterTitle}
                onClick={() => onSelectEvidence(primaryOverlay.evidence)}
                className={buttonClassName}
                style={buttonStyle}
              />
            ) : null;
          })}
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
 * Find the nearest Base UI scroll viewport that should drive page lazy rendering.
 */
function findScrollAreaViewport(node: HTMLElement): Element | null {
  return node.closest('[data-slot="scroll-area-viewport"]');
}

/**
 * Group positioned extraction evidence by PDF page with display labels.
 */
function buildOverlaysByPage(items: ExtractionItem[]): Map<number, EvidenceOverlay[]> {
  const overlaysByPage = new Map<number, EvidenceOverlay[]>();

  for (const item of items) {
    for (const evidence of item.evidence) {
      if (!evidence.page || !evidence.bbox) {
        continue;
      }
      const pageOverlays = overlaysByPage.get(evidence.page) ?? [];
      pageOverlays.push({
        evidence,
        label: item.title || evidence.objectId,
        slotLabel: item.slotLabel,
      });
      overlaysByPage.set(evidence.page, pageOverlays);
    }
  }

  return overlaysByPage;
}

/**
 * Convert all page evidence boxes into deduplicated viewport overlay clusters.
 */
function calculateOverlayClusters(
  overlays: EvidenceOverlay[],
  viewport: PdfViewport | null,
): EvidenceOverlayCluster[] {
  if (!viewport) {
    return [];
  }

  const clustersByRect = new Map<string, EvidenceOverlayCluster>();

  for (const overlay of overlays) {
    const rect = calculateHighlightRect(overlay.evidence, viewport);
    if (!rect) {
      continue;
    }

    const key = getRectClusterKey(rect);
    const cluster = clustersByRect.get(key);
    if (cluster) {
      cluster.overlays.push(overlay);
      continue;
    }

    clustersByRect.set(key, {
      rect,
      overlays: [overlay],
    });
  }

  return Array.from(clustersByRect.values());
}

/**
 * Round overlay geometry so tiny PDF viewport differences do not split one visual target.
 */
function getRectClusterKey(rect: HighlightRect): string {
  return [
    Math.round(rect.left),
    Math.round(rect.top),
    Math.round(rect.width),
    Math.round(rect.height),
  ].join(":");
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
