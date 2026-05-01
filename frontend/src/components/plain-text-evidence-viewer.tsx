import { ScrollArea } from "@/components/ui/scroll-area";
import { useTextEvidence } from "@/hooks/use-text-evidence";
import type { ExtractionEvidence, ExtractionItem } from "@/lib/evidence";

interface PlainTextEvidenceViewerProps {
  text: string;
  items: ExtractionItem[];
  selectedEvidence: ExtractionEvidence | null;
  onSelectEvidence: (evidence: ExtractionEvidence) => void;
}

/**
 * Render plain text with textSpan evidence highlights.
 *
 * Renders the original text content inside a <pre> element and overlays
 * evidence highlights using the useTextEvidence hook.
 */
export function PlainTextEvidenceViewer({
  text,
  items,
  selectedEvidence,
  onSelectEvidence,
}: PlainTextEvidenceViewerProps) {
  const containerRef = useTextEvidence(items, selectedEvidence, onSelectEvidence);

  return (
    <ScrollArea className="h-full">
      <pre
        ref={containerRef}
        className="whitespace-pre-wrap px-5 py-4 font-mono text-sm leading-6 text-foreground"
      >
        {text}
      </pre>
    </ScrollArea>
  );
}
