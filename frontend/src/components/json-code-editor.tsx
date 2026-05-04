import { useEffect, useMemo, useRef } from "react";
import CodeMirror, { type ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { json, jsonParseLinter } from "@codemirror/lang-json";
import { linter } from "@codemirror/lint";
import { searchKeymap, highlightSelectionMatches } from "@codemirror/search";
import {
  bracketMatching,
  defaultHighlightStyle,
  foldGutter,
  indentOnInput,
  syntaxHighlighting,
} from "@codemirror/language";
import {
  drawSelection,
  dropCursor,
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
} from "@codemirror/view";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import type { ExtractionItem } from "@/lib/evidence";

interface JsonCodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  selectedItem: ExtractionItem | null;
}

/**
 * JSON code editor backed by CodeMirror 6 with syntax highlighting,
 * folding, bracket matching, linting, and extract-item jump-to.
 */
export function JsonCodeEditor({
  value,
  onChange,
  selectedItem,
}: JsonCodeEditorProps) {
  const editorRef = useRef<ReactCodeMirrorRef>(null);
  const valueRef = useRef(value);
  valueRef.current = value;

  const extensions = useMemo(
    () => [
      lineNumbers(),
      foldGutter(),
      history(),
      drawSelection(),
      dropCursor(),
      indentOnInput(),
      bracketMatching(),
      highlightActiveLine(),
      highlightActiveLineGutter(),
      highlightSelectionMatches(),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      json(),
      linter(jsonParseLinter()),
      keymap.of([
        indentWithTab,
        ...defaultKeymap,
        ...historyKeymap,
        ...searchKeymap,
      ]),
      EditorView.lineWrapping,
      EditorView.theme({
        "&": {
          height: "100%",
          fontSize: "13px",
          backgroundColor: "hsl(var(--muted) / 0.1)",
        },
        ".cm-scroller": {
          fontFamily:
            "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        },
        ".cm-gutters": {
          backgroundColor: "hsl(var(--muted) / 0.2)",
          borderRight: "1px solid hsl(var(--border))",
        },
        ".cm-activeLine": {
          backgroundColor: "hsl(var(--muted) / 0.35)",
        },
        ".cm-activeLineGutter": {
          backgroundColor: "hsl(var(--muted) / 0.35)",
        },
      }),
    ],
    [],
  );

  /** Jump to and select the JSON object for the currently selected extraction item. */
  useEffect(() => {
    if (!selectedItem) {
      return;
    }

    let cancelled = false;

    // Double RAF ensures CodeMirror's useLayoutEffect has run and the EditorView
    // ref is populated before we attempt the jump — especially on first mount.
    const frameId = requestAnimationFrame(() => {
      const innerId = requestAnimationFrame(() => {
        if (cancelled) return;

        const view = editorRef.current?.view;
        if (!view) return;

        const range = findJsonItemRange(valueRef.current, selectedItem);
        if (!range) {
          console.warn(
            `JsonCodeEditor: 无法定位 "${selectedItem.slot}" / "${selectedItem.id}" 在 JSON 中的位置。`,
          );
          return;
        }

        view.dispatch({
          selection: {
            anchor: range.start,
            head: range.end,
          },
          effects: EditorView.scrollIntoView(range.start, {
            y: "center",
          }),
        });

        view.focus();
      });

      if (cancelled) cancelAnimationFrame(innerId);
    });

    return () => {
      cancelled = true;
      cancelAnimationFrame(frameId);
    };
  }, [selectedItem]);

  return (
    <div className="h-full min-h-0 overflow-hidden rounded-md border bg-muted/10">
      <CodeMirror
        className="h-full"
        ref={editorRef}
        value={value}
        height="100%"
        basicSetup={false}
        extensions={extensions}
        onChange={onChange}
        placeholder="这里显示结构化提取结果，可直接修正 JSON。"
      />
    </div>
  );
}

/**
 * Locate the character range of a selected extraction item inside formatted JSON.
 */
function findJsonItemRange(
  jsonText: string,
  item: ExtractionItem,
): { start: number; end: number } | null {
  const slotKeyIndex = jsonText.indexOf(`"${item.slot}"`);
  if (slotKeyIndex < 0) {
    return null;
  }

  const arrayStart = jsonText.indexOf("[", slotKeyIndex);
  if (arrayStart < 0) {
    return null;
  }

  const arrayEnd = findMatchingJsonToken(jsonText, arrayStart, "[", "]");
  if (arrayEnd < 0) {
    return null;
  }

  const idPattern = new RegExp(`"id"\\s*:\\s*"${escapeRegExp(item.id)}"`);
  let cursor = arrayStart + 1;

  while (cursor < arrayEnd) {
    const objectStart = findNextJsonObjectStart(jsonText, cursor, arrayEnd);
    if (objectStart < 0) {
      return null;
    }

    const objectEnd = findMatchingJsonToken(jsonText, objectStart, "{", "}");
    if (objectEnd < 0 || objectEnd > arrayEnd) {
      return null;
    }

    if (idPattern.test(jsonText.slice(objectStart, objectEnd + 1))) {
      return { start: objectStart, end: objectEnd + 1 };
    }

    cursor = objectEnd + 1;
  }

  return null;
}

/**
 * Walk JSON tokens to locate the matching close bracket, skipping strings.
 */
function findMatchingJsonToken(
  text: string,
  start: number,
  openToken: string,
  closeToken: string,
): number {
  let depth = 0;
  let inString = false;
  let escaping = false;

  for (let index = start; index < text.length; index += 1) {
    const char = text[index];

    if (inString) {
      if (escaping) {
        escaping = false;
      } else if (char === "\\") {
        escaping = true;
      } else if (char === "\"") {
        inString = false;
      }
      continue;
    }

    if (char === "\"") {
      inString = true;
    } else if (char === openToken) {
      depth += 1;
    } else if (char === closeToken) {
      depth -= 1;
      if (depth === 0) {
        return index;
      }
    }
  }

  return -1;
}

/**
 * Find the next object start outside quoted string content.
 */
function findNextJsonObjectStart(
  text: string,
  from: number,
  maxIndex: number,
): number {
  let inString = false;
  let escaping = false;

  for (let index = from; index <= maxIndex; index += 1) {
    const char = text[index];

    if (inString) {
      if (escaping) {
        escaping = false;
      } else if (char === "\\") {
        escaping = true;
      } else if (char === "\"") {
        inString = false;
      }
      continue;
    }

    if (char === "\"") {
      inString = true;
    } else if (char === "{") {
      return index;
    }
  }

  return -1;
}

/**
 * Escape special regex characters in a string.
 */
function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
