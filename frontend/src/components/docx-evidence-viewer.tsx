import { useEffect, useMemo, useRef, type HTMLAttributes, type KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { DocumentElement, DocumentIR } from "@/lib/api";
import {
  evidenceMatches,
  type ExtractionEvidence,
  type ExtractionItem,
} from "@/lib/evidence";
import { cn } from "@/lib/utils";

interface DocxEvidenceViewerProps {
  documentIr: DocumentIR | null | undefined;
  items: ExtractionItem[];
  selectedEvidence: ExtractionEvidence | null;
  onSelectEvidence: (evidence: ExtractionEvidence) => void;
}

interface TextPosition {
  node: Text;
  offset: number;
}

interface EvidenceTarget {
  evidence: ExtractionEvidence;
  label: string;
  slotLabel: string;
}

const HIGHLIGHT_CLASS = "evidence-highlight";
const HIGHLIGHT_SELECTED_CLASS = "evidence-highlight-selected";
const BLOCK_SELECTED_CLASS = "evidence-block-highlight";

/**
 * Sanitize schema for markdown rendering with table support.
 */
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
    code: [...(defaultSchema.attributes?.code ?? []), ["className", /^language-/]],
    pre: [...(defaultSchema.attributes?.pre ?? []), ["className"]],
    table: [...(defaultSchema.attributes?.table ?? []), ["className"]],
    td: [...(defaultSchema.attributes?.td ?? []), "align", "colspan", "colSpan", "rowspan", "rowSpan"],
    th: [...(defaultSchema.attributes?.th ?? []), "align", "colspan", "colSpan", "rowspan", "rowSpan"],
  },
};

/**
 * Render DOCX source content from backend Document IR and locate evidence by element id.
 */
export function DocxEvidenceViewer({
  documentIr,
  items,
  selectedEvidence,
  onSelectEvidence,
}: DocxEvidenceViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const elementRefs = useRef(new Map<string, HTMLElement>());
  const elements = useMemo(
    () => normalizeElements(documentIr?.elements),
    [documentIr?.elements],
  );
  const targetsByElementId = useMemo(
    () => buildTargetsByElementId(items, elements),
    [items, elements],
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    cleanupEvidenceMarks(container);
    clearSelectedBlocks(container);

    if (!selectedEvidence?.elementId) {
      return;
    }

    const block = elementRefs.current.get(selectedEvidence.elementId);
    if (!block) {
      return;
    }

    block.classList.add(BLOCK_SELECTED_CLASS);
    if (selectedEvidence.textSpan) {
      highlightTextInsideBlock(block, selectedEvidence.textSpan, {
        evidenceObjectId: selectedEvidence.objectId,
        evidenceElementId: selectedEvidence.elementId,
      });
    }

    window.setTimeout(() => {
      block.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 0);
  }, [selectedEvidence]);

  if (elements.length === 0) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center px-6 text-center text-sm text-muted-foreground">
        暂无可定位 DOCX 内容
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div ref={containerRef} className="docx-preview mx-auto max-w-4xl px-5 py-4">
        {elements.map((element) => {
          const targets = targetsByElementId.get(element.element_id) ?? [];
          const selected = targets.some((target) => evidenceMatches(target.evidence, selectedEvidence));

          return (
            <SourceElementBlock
              key={element.element_id}
              element={element}
              targets={targets}
              selected={selected}
              onRegister={(node) => registerElementRef(elementRefs.current, element.element_id, node)}
              onSelectEvidence={onSelectEvidence}
            />
          );
        })}
      </div>
    </ScrollArea>
  );
}

/**
 * Render one IR element as a source block with stable element-id metadata.
 * Supports multiple evidence targets via dropdown menu.
 */
function SourceElementBlock({
  element,
  targets,
  selected,
  onRegister,
  onSelectEvidence,
}: {
  element: DocumentElement;
  targets: EvidenceTarget[];
  selected: boolean;
  onRegister: (node: HTMLElement | null) => void;
  onSelectEvidence: (evidence: ExtractionEvidence) => void;
}) {
  const interactive = targets.length > 0;
  const hasMultipleTargets = targets.length > 1;
  const title = targets.map((target) => `${target.slotLabel}: ${target.label}`).join("\n");

  const elementContent = renderElementContent(element, {
    ref: onRegister,
    interactive,
    selected,
    title,
  });

  // Multiple targets: show dropdown menu
  if (hasMultipleTargets) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger className="w-full cursor-pointer">
          {elementContent}
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-64">
          {targets.map((target, index) => (
            <DropdownMenuItem
              key={`${target.evidence.objectId}-${index}`}
              onClick={() => onSelectEvidence(target.evidence)}
              className="flex-col items-start gap-0.5"
            >
              <span className="max-w-full truncate text-sm font-medium">{target.label}</span>
              <span className="max-w-full truncate font-mono text-[11px] text-muted-foreground">
                {target.slotLabel} / {target.evidence.objectId}
              </span>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  // Single target: clickable to select
  if (targets.length === 1) {
    return (
      <div onClick={() => onSelectEvidence(targets[0].evidence)} className="cursor-pointer">
        {elementContent}
      </div>
    );
  }

  // No targets: static display
  return elementContent;
}

/**
 * Render the actual element content (heading, table, or paragraph).
 */
function renderElementContent(
  element: DocumentElement,
  {
    ref,
    interactive,
    selected,
    title,
  }: {
    ref: (node: HTMLElement | null) => void;
    interactive: boolean;
    selected: boolean;
    title: string;
  },
) {
  const commonProps = {
    ref,
    "data-element-id": element.element_id,
    role: interactive ? "button" : undefined,
    tabIndex: interactive ? 0 : undefined,
    title: title || undefined,
    onKeyDown: (event: KeyboardEvent<HTMLElement>) => {
      if (!interactive || (event.key !== "Enter" && event.key !== " ")) {
        return;
      }
      event.preventDefault();
      // Let parent handle the click
      (event.currentTarget as HTMLElement).click();
    },
    className: cn(
      "evidence-source-block rounded-md border border-transparent px-3 py-2 text-foreground transition-colors",
      interactive && "cursor-pointer hover:border-amber-400/60 hover:bg-amber-200/10",
      selected && "border-primary bg-primary/10 ring-2 ring-primary/30",
    ),
  };

  if (element.element_type === "heading") {
    return renderHeadingElement(element, commonProps);
  }

  if (element.element_type === "table") {
    return (
      <div {...commonProps} className={cn(commonProps.className, "prose prose-sm max-w-none")}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeRaw, [rehypeSanitize, markdownSanitizeSchema], rehypeKatex, rehypeHighlight]}
        >
          {element.markdown || element.text || ""}
        </ReactMarkdown>
      </div>
    );
  }

  return (
    <p {...commonProps} className={cn(commonProps.className, "whitespace-pre-wrap text-sm leading-6")}>
      {element.text || element.markdown || ""}
    </p>
  );
}

/**
 * Render an IR heading with a level inferred from its section depth.
 */
function renderHeadingElement(
  element: DocumentElement,
  props: HTMLAttributes<HTMLElement> & { ref: (node: HTMLElement | null) => void },
) {
  const level = Math.min(Math.max(element.section_path.length || 2, 1), 3);
  const text = element.text || element.markdown || "";
  if (level === 1) {
    return <h1 {...props} className={cn(props.className, "text-xl font-semibold")}>{text}</h1>;
  }
  if (level === 2) {
    return <h2 {...props} className={cn(props.className, "text-lg font-semibold")}>{text}</h2>;
  }
  return <h3 {...props} className={cn(props.className, "text-base font-semibold")}>{text}</h3>;
}

/**
 * Return stable, renderable IR elements sorted by document order.
 */
function normalizeElements(elements: DocumentElement[] | undefined): DocumentElement[] {
  if (!elements?.length) {
    return [];
  }
  return [...elements]
    .filter((element) => element.element_id && (element.text || element.markdown))
    .sort((left, right) => left.order - right.order);
}

/**
 * Group evidence entries by their primary IR element id.
 */
function buildTargetsByElementId(
  items: ExtractionItem[],
  elements: DocumentElement[],
): Map<string, EvidenceTarget[]> {
  const elementIds = new Set(elements.map((element) => element.element_id));
  const targetsByElementId = new Map<string, EvidenceTarget[]>();

  for (const item of items) {
    for (const evidence of item.evidence) {
      if (!evidence.elementId || !elementIds.has(evidence.elementId)) {
        continue;
      }
      const targets = targetsByElementId.get(evidence.elementId) ?? [];
      targets.push({
        evidence,
        label: item.title || evidence.objectId,
        slotLabel: item.slotLabel,
      });
      targetsByElementId.set(evidence.elementId, targets);
    }
  }

  return targetsByElementId;
}

/**
 * Register or clear an element DOM ref for evidence scrolling.
 */
function registerElementRef(
  refs: Map<string, HTMLElement>,
  elementId: string,
  node: HTMLElement | null,
) {
  if (node) {
    refs.set(elementId, node);
    return;
  }
  refs.delete(elementId);
}

/**
 * Remove selected styling from all source blocks in a container.
 */
function clearSelectedBlocks(container: HTMLElement): void {
  container.querySelectorAll(`.${BLOCK_SELECTED_CLASS}`).forEach((block) => {
    block.classList.remove(BLOCK_SELECTED_CLASS);
  });
}

/**
 * Highlight selected evidence text inside one IR block.
 */
function highlightTextInsideBlock(
  block: HTMLElement,
  searchText: string,
  dataset: Record<string, string>,
): void {
  const normalizedSearch = normalizeSearchText(searchText);
  if (!normalizedSearch) {
    return;
  }

  const index = buildNormalizedTextIndex(block);
  const matchIndex = index.text.indexOf(normalizedSearch);
  if (matchIndex === -1) {
    return;
  }

  const start = index.positions[matchIndex];
  const end = index.positions[matchIndex + normalizedSearch.length - 1];
  if (!start || !end) {
    return;
  }

  try {
    const range = document.createRange();
    range.setStart(start.node, start.offset);
    range.setEnd(end.node, end.offset + 1);
    wrapRange(range, dataset);
  } catch {
    // Some browser-generated ranges around table/pre text can be invalid.
  }
}

/**
 * Build normalized searchable text while preserving original DOM offsets.
 */
function buildNormalizedTextIndex(block: HTMLElement): { text: string; positions: TextPosition[] } {
  const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
  const positions: TextPosition[] = [];
  let text = "";
  let pendingWhitespace: TextPosition | null = null;
  let node: Text | null;

  while ((node = walker.nextNode() as Text | null)) {
    const value = node.textContent || "";
    for (let offset = 0; offset < value.length; offset += 1) {
      const character = value[offset];
      if (/\s/.test(character)) {
        pendingWhitespace ??= { node, offset };
        continue;
      }

      if (pendingWhitespace && text.length > 0) {
        text += " ";
        positions.push(pendingWhitespace);
      }
      pendingWhitespace = null;
      text += character;
      positions.push({ node, offset });
    }
  }

  return { text, positions };
}

/**
 * Normalize whitespace for evidence text comparison.
 */
function normalizeSearchText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

/**
 * Wrap a matched text range with the evidence mark element.
 */
function wrapRange(range: Range, dataset: Record<string, string>): void {
  const mark = document.createElement("mark");
  mark.className = `${HIGHLIGHT_CLASS} ${HIGHLIGHT_SELECTED_CLASS}`;
  Object.entries(dataset).forEach(([key, value]) => {
    mark.dataset[key] = value;
  });
  mark.append(range.extractContents());
  range.insertNode(mark);
}

/**
 * Remove all evidence marks without dropping their original text.
 */
function cleanupEvidenceMarks(container: HTMLElement): void {
  const marks = container.querySelectorAll(`mark.${HIGHLIGHT_CLASS}`);
  for (const mark of marks) {
    const parent = mark.parentNode;
    if (!parent) {
      continue;
    }
    while (mark.firstChild) {
      parent.insertBefore(mark.firstChild, mark);
    }
    parent.removeChild(mark);
    parent.normalize();
  }
}
