import { useCallback, useEffect, useRef, useState } from "react";
import * as mammoth from "mammoth";
import { FileText, Loader2, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";

interface DocxPreviewProps {
  blob: Blob;
  onHtmlReady?: (html: string) => void;
}

/**
 * Convert a DOCX blob to styled HTML using mammoth.js for inline preview.
 */
export function DocxPreview({ blob, onHtmlReady }: DocxPreviewProps) {
  const [html, setHtml] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const htmlReadyRef = useRef(false);

  useEffect(() => {
    let disposed = false;
    htmlReadyRef.current = false;

    async function convert() {
      setLoadError(null);
      setHtml(null);

      try {
        const arrayBuffer = await blob.arrayBuffer();
        const result = await mammoth.convertToHtml(
          { arrayBuffer },
          {
            styleMap: [
              "p[style-name='Heading 1'] => h1:fresh",
              "p[style-name='Heading 2'] => h2:fresh",
              "p[style-name='Heading 3'] => h3:fresh",
              "p[style-name='Heading 4'] => h4:fresh",
              "p[style-name='heading 1'] => h1:fresh",
              "p[style-name='heading 2'] => h2:fresh",
              "p[style-name='heading 3'] => h3:fresh",
              "p[style-name='heading 4'] => h4:fresh",
              "r[style-name='Strong'] => strong",
              "r[style-name='Emphasis'] => em",
            ],
          },
        );

        if (!disposed) {
          setHtml(result.value);
          htmlReadyRef.current = true;
          onHtmlReady?.(result.value);
        }
      } catch {
        if (!disposed) {
          setLoadError("DOCX 解析失败");
        }
      }
    }

    convert();

    return () => {
      disposed = true;
    };
  }, [blob, onHtmlReady, retryKey]);

  const handleRetry = useCallback(() => {
    setRetryKey((value) => value + 1);
  }, []);

  if (loadError) {
    return (
      <div className="flex h-full min-h-0 flex-col items-center justify-center gap-3 px-6 text-center text-sm text-muted-foreground">
        <FileText className="h-10 w-10 opacity-40" />
        <div>
          <p className="font-medium text-foreground">{loadError}</p>
          <p className="mt-1">该文件可能已损坏或使用了不受支持的格式。</p>
        </div>
        <Button variant="secondary" size="sm" onClick={handleRetry}>
          <RotateCcw data-icon="inline-start" />
          重试
        </Button>
      </div>
    );
  }

  if (!html) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在解析 DOCX...
      </div>
    );
  }

  return (
    <div
      className="docx-preview prose prose-sm max-w-none px-5 py-4 text-foreground prose-headings:font-semibold prose-pre:bg-muted"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
