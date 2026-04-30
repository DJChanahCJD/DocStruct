import { useEffect, useMemo, useRef } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { ScrollArea } from "@/components/ui/scroll-area";
import type { DocumentElement, DocumentIR } from "@/lib/api";
import {
  evidenceMatches,
  type ExtractionEvidence,
  type ExtractionItem,
} from "@/lib/evidence";
import { cn } from "@/lib/utils";

interface TextEvidenceViewerProps {
  parsedContent: string | null | undefined;
  documentIr: DocumentIR | null | undefined;
  items: ExtractionItem[];
  selectedEvidence: ExtractionEvidence | null;
  onSelectEvidence: (evidence: ExtractionEvidence) => void;
}

interface EvidenceTarget {
  evidence: ExtractionEvidence;
  label: string;
  slotLabel: string;
}

const markdownSanitizeSchema = {
  ...defaultSchema,
  tagNames: [
    ...(defaultSchema.tagNames ?? []),
    "br",
    "caption",
    "code",
    "col",
    "colgroup",
    "kbd",
    "pre",
    "samp",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
  ],
  attributes: {
    ...defaultSchema.attributes,
    code: [
      ...(defaultSchema.attributes?.code ?? []),
      ["className", /^language-/],
    ],
    pre: [
      ...(defaultSchema.attributes?.pre ?? []),
      ["className"],
    ],
    table: [
      ...(defaultSchema.attributes?.table ?? []),
      ["className"],
    ],
    td: [
      ...(defaultSchema.attributes?.td ?? []),
      "align",
      "colspan",
      "colSpan",
      "rowspan",
      "rowSpan",
    ],
    th: [
      ...(defaultSchema.attributes?.th ?? []),
      "align",
      "colspan",
      "colSpan",
      "rowspan",
      "rowSpan",
    ],
  },
};

/**
 * Render parsed text-like documents and scroll to evidence-bound IR elements.
 */
export function TextEvidenceViewer({
  parsedContent,
  documentIr,
  items,
  selectedEvidence,
  onSelectEvidence,
}: TextEvidenceViewerProps) {
  const elementRefs = useRef(new Map<string, HTMLDivElement>());
  const elements = useMemo(
    () => normalizeElements(documentIr?.elements, parsedContent),
    [documentIr?.elements, parsedContent],
  );
  const targetsByElementId = useMemo(
    () => buildTargetsByElementId(items, elements),
    [items, elements],
  );
  const selectedElementId = useMemo(
    () => findEvidenceElementId(selectedEvidence, elements),
    [elements, selectedEvidence],
  );
  const interactivePreview = items.length > 0;

  useEffect(() => {
    if (!interactivePreview || !selectedElementId) {
      return;
    }

    window.setTimeout(() => {
      elementRefs.current.get(selectedElementId)?.scrollIntoView({
        block: "center",
        behavior: "smooth",
      });
    }, 0);
  }, [interactivePreview, selectedElementId]);

  if (!interactivePreview) {
    const markdown = parsedContent?.trim();
    if (!markdown) {
      return <EmptyTextPreview />;
    }

    return (
      <ScrollArea className="h-full">
        <div className="mx-auto max-w-4xl px-5 py-4">
          <MarkdownPreview markdown={markdown} />
        </div>
      </ScrollArea>
    );
  }

  if (elements.length === 0) {
    return <EmptyTextPreview />;
  }

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto max-w-4xl px-5 py-4">
        {elements.map((element) => {
          const targets = targetsByElementId.get(element.element_id) ?? [];
          const selected = targets.some((target) => evidenceMatches(target.evidence, selectedEvidence));
          const interactive = targets.length > 0;
          const title = targets.map((target) => `${target.slotLabel}: ${target.label}`).join("\n");

          return (
            <div
              key={element.element_id}
              ref={(node) => registerElementRef(elementRefs.current, element.element_id, node)}
              role={interactive ? "button" : undefined}
              tabIndex={interactive ? 0 : undefined}
              title={title || undefined}
              onClick={() => {
                if (targets[0]) {
                  onSelectEvidence(targets[0].evidence);
                }
              }}
              onKeyDown={(event) => {
                if (!targets[0] || (event.key !== "Enter" && event.key !== " ")) {
                  return;
                }
                event.preventDefault();
                onSelectEvidence(targets[0].evidence);
              }}
              className={cn(
                "rounded-md border border-transparent px-3 py-2 transition-colors",
                interactive && "cursor-pointer hover:border-amber-400/60 hover:bg-amber-200/10",
                selected && "border-primary bg-primary/10 ring-2 ring-primary/30",
              )}
            >
              <MarkdownPreview markdown={renderElementMarkdown(element)} />
            </div>
          );
        })}
      </div>
    </ScrollArea>
  );
}

/**
 * Render the empty state shared by text previews.
 */
function EmptyTextPreview() {
  return (
    <div className="flex h-full min-h-0 items-center justify-center px-6 text-center text-sm text-muted-foreground">
      暂无可预览文本
    </div>
  );
}

/**
 * Render Markdown with GFM, math, code highlighting, and safe embedded HTML.
 */
function MarkdownPreview({ markdown }: { markdown: string }) {
  return (
    <div className="prose prose-sm max-w-none text-foreground prose-headings:font-semibold prose-pre:bg-muted">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeRaw, [rehypeSanitize, markdownSanitizeSchema], rehypeKatex, rehypeHighlight]}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}

/**
 * Register or clear a rendered element node for evidence scrolling.
 */
function registerElementRef(
  refs: Map<string, HTMLDivElement>,
  elementId: string,
  node: HTMLDivElement | null,
) {
  if (node) {
    refs.set(elementId, node);
    return;
  }
  refs.delete(elementId);
}

/**
 * Prefer backend IR blocks, falling back to one whole-document Markdown block.
 */
function normalizeElements(
  elements: DocumentElement[] | undefined,
  parsedContent: string | null | undefined,
): DocumentElement[] {
  if (elements?.length) {
    return [...elements].sort((left, right) => left.order - right.order);
  }

  const text = parsedContent?.trim();
  if (!text) {
    return [];
  }

  return [{
    element_id: "parsed-content",
    element_type: "paragraph",
    text,
    markdown: text,
    section_path: [],
    page: null,
    bbox: null,
    order: 0,
    metadata: {},
  }];
}

/**
 * Group extraction evidence by the preview element it can locate.
 */
function buildTargetsByElementId(
  items: ExtractionItem[],
  elements: DocumentElement[],
): Map<string, EvidenceTarget[]> {
  const targetsByElementId = new Map<string, EvidenceTarget[]>();

  for (const item of items) {
    for (const evidence of item.evidence) {
      const elementId = findEvidenceElementId(evidence, elements);
      if (!elementId) {
        continue;
      }

      const targets = targetsByElementId.get(elementId) ?? [];
      targets.push({
        evidence,
        label: item.title || evidence.objectId,
        slotLabel: item.slotLabel,
      });
      targetsByElementId.set(elementId, targets);
    }
  }

  return targetsByElementId;
}

/**
 * Resolve evidence to an IR element by id first, then by text span.
 */
function findEvidenceElementId(
  evidence: ExtractionEvidence | null,
  elements: DocumentElement[],
): string | null {
  if (!evidence) {
    return null;
  }

  if (evidence.elementId && elements.some((element) => element.element_id === evidence.elementId)) {
    return evidence.elementId;
  }

  const textSpan = evidence.textSpan?.trim();
  if (!textSpan) {
    return null;
  }

  const normalizedSpan = normalizeSearchText(textSpan);
  const matchedElement = elements.find((element) =>
    normalizeSearchText(`${element.text ?? ""}\n${element.markdown ?? ""}`).includes(normalizedSpan),
  );
  return matchedElement?.element_id ?? null;
}

/**
 * Render the most faithful Markdown fragment available for one IR element.
 */
function renderElementMarkdown(element: DocumentElement): string {
  return element.markdown || element.text || "";
}

/**
 * Normalize whitespace so text-span fallback survives Markdown formatting.
 */
function normalizeSearchText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}
