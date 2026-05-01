import { useCallback, useEffect, useRef, useState } from "react";
import { type ExtractionEvidence, type ExtractionItem } from "@/lib/evidence";

const HIGHLIGHT_CLASS = "evidence-highlight";
const HIGHLIGHT_SELECTED_CLASS = "evidence-highlight-selected";

interface TextPosition {
  node: Text;
  offset: number;
}

interface NormalizedTextIndex {
  text: string;
  positions: TextPosition[];
}

/**
 * Normalize whitespace for text comparison by collapsing all whitespace into single spaces.
 */
function normalizeWhitespace(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

/**
 * Build a normalized text stream for a container while retaining DOM offsets.
 */
function buildNormalizedTextIndex(container: HTMLElement): NormalizedTextIndex {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
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
 * Wrap a DOM range in a mark while preserving any nested inline structure.
 */
function wrapRange(range: Range, dataset: Record<string, string>): void {
  const mark = document.createElement("mark");
  mark.className = HIGHLIGHT_CLASS;
  Object.entries(dataset).forEach(([key, value]) => {
    mark.dataset[key] = value;
  });

  mark.append(range.extractContents());
  range.insertNode(mark);
}

/**
 * Apply highlights in a DOM container for normalized textSpan matches.
 */
function applyTextHighlights(
  container: HTMLElement,
  searchText: string,
  dataset: Record<string, string>,
): void {
  const normalizedSearch = normalizeWhitespace(searchText);
  if (!normalizedSearch) {
    return;
  }

  const index = buildNormalizedTextIndex(container);
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
    // Invalid DOM ranges can occur around unusual converted Office markup.
  }
}

/**
 * Remove all highlight marks created by this hook from the container.
 */
function cleanupHighlights(container: HTMLElement): void {
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

/**
 * Tear down listener and highlights for a container.
 */
function teardownContainer(container: HTMLElement): void {
  cleanupHighlights(container);
}

/**
 * In a rendered DOM container, find textSpans from extraction evidence and highlight them.
 *
 * After React renders content (Markdown, mammoth HTML, plain text), this hook
 * walks the container's text nodes, matches evidence textSpans (with whitespace
 * normalization fallback), and wraps matches in `<mark>` elements.
 *
 * Clicking a highlight calls onSelectEvidence. When selectedEvidence changes,
 * the corresponding mark gets a selected class and scrolls into view.
 *
 * Returns a callback ref to attach to the container element. This pattern
 * ensures highlighting works even when the container mounts asynchronously
 * (e.g. after mammoth.js conversion completes).
 */
export function useTextEvidence(
  items: ExtractionItem[],
  selectedEvidence: ExtractionEvidence | null,
  onSelectEvidence: (evidence: ExtractionEvidence) => void,
): (node: HTMLElement | null) => void {
  const [node, setNode] = useState<HTMLElement | null>(null);
  const onSelectRef = useRef(onSelectEvidence);

  useEffect(() => {
    onSelectRef.current = onSelectEvidence;
  }, [onSelectEvidence]);

  const refCallback = useCallback((nextNode: HTMLElement | null) => {
    setNode(nextNode);
  }, []);

  useEffect(() => {
    const container = node;
    if (!container) {
      return;
    }

    cleanupHighlights(container);

    if (items.length === 0) {
      return;
    }

    for (const item of items) {
      for (const ev of item.evidence) {
        if (!ev.textSpan) {
          continue;
        }
        applyTextHighlights(container, ev.textSpan, {
          evidenceObjectId: ev.objectId,
          evidenceElementId: ev.elementId || "",
        });
      }
    }

    if (selectedEvidence) {
      const marks = container.querySelectorAll<HTMLElement>(`mark.${HIGHLIGHT_CLASS}`);
      let selectedMark: HTMLElement | null = null;
      for (const mark of marks) {
        const objectId = mark.dataset.evidenceObjectId;
        const elementId = mark.dataset.evidenceElementId;
        const matches =
          objectId === selectedEvidence.objectId &&
          (elementId || "") === (selectedEvidence.elementId || "");

        if (matches) {
          mark.classList.add(HIGHLIGHT_SELECTED_CLASS);
          selectedMark = mark;
        } else {
          mark.classList.remove(HIGHLIGHT_SELECTED_CLASS);
        }
      }

      if (selectedMark) {
        selectedMark.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    }

    const handleClick = (event: MouseEvent) => {
      const mark = (event.target as HTMLElement).closest<HTMLElement>(`mark.${HIGHLIGHT_CLASS}`);
      if (!mark) {
        return;
      }
      const objectId = mark.dataset.evidenceObjectId;
      const elementId = mark.dataset.evidenceElementId || null;
      if (!objectId) {
        return;
      }

      for (const item of items) {
        for (const ev of item.evidence) {
          if (
            ev.objectId === objectId &&
            (ev.elementId || "") === (elementId || "")
          ) {
            onSelectRef.current(ev);
            return;
          }
        }
      }
    };
    container.addEventListener("click", handleClick);

    return () => {
      container.removeEventListener("click", handleClick);
      teardownContainer(container);
    };
  }, [node, items, selectedEvidence]);

  return refCallback;
}
