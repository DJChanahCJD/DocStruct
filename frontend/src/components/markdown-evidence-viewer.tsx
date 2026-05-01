import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { ScrollArea } from "@/components/ui/scroll-area";
import { useTextEvidence } from "@/hooks/use-text-evidence";
import type { ExtractionEvidence, ExtractionItem } from "@/lib/evidence";

interface MarkdownEvidenceViewerProps {
  markdown: string;
  items: ExtractionItem[];
  selectedEvidence: ExtractionEvidence | null;
  onSelectEvidence: (evidence: ExtractionEvidence) => void;
}

/**
 * Render raw Markdown with textSpan evidence highlights.
 *
 * Renders the original Markdown content through ReactMarkdown and overlays
 * evidence highlights using the useTextEvidence hook.
 */
export function MarkdownEvidenceViewer({
  markdown,
  items,
  selectedEvidence,
  onSelectEvidence,
}: MarkdownEvidenceViewerProps) {
  const containerRef = useTextEvidence(items, selectedEvidence, onSelectEvidence);

  return (
    <ScrollArea className="h-full">
      <div
        ref={containerRef}
        className="prose prose-sm max-w-none px-5 py-4 text-foreground prose-headings:font-semibold prose-pre:bg-muted"
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeKatex, rehypeHighlight]}
        >
          {markdown}
        </ReactMarkdown>
      </div>
    </ScrollArea>
  );
}
