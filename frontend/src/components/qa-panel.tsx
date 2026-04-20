import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, KeyboardEvent } from "react";
import { Copy, FileText, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useAskQuestion, useDocuments } from "@/hooks/use-api";
import type { CitationItem, DocumentRecord } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";

interface QaPanelProps {
  mentionSeed?: {
    docId: number;
    docName: string;
    nonce: number;
  } | null;
  activeModelId?: string | null;
  activeModelLabel?: string;
  onOpenCitation: (citation: CitationItem) => void;
}

interface KnownMention {
  docId: number;
  label: string;
}

interface ActiveMention {
  query: string;
  start: number;
  end: number;
}

interface ParsedMentionResult {
  cleanedQuestion: string;
  docIds: number[];
  docLabels: string[];
  unresolvedTokens: string[];
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeText(value: string) {
  return value.trim().toLowerCase();
}

function getActiveMention(text: string, cursor: number): ActiveMention | null {
  const beforeCursor = text.slice(0, cursor);
  const match = beforeCursor.match(/(^|\s)@([^\n\r@]*)$/);
  if (!match) {
    return null;
  }

  const query = match[2];
  const start = beforeCursor.length - query.length - 1;
  return { query, start, end: cursor };
}

function uniqueMentions(mentions: KnownMention[]) {
  const seen = new Set<number>();
  return mentions.filter((mention) => {
    if (seen.has(mention.docId)) {
      return false;
    }
    seen.add(mention.docId);
    return true;
  });
}

function parseMentionReferences(
  question: string,
  knownMentions: KnownMention[],
  docs: DocumentRecord[],
): ParsedMentionResult {
  const docIds: number[] = [];
  const docLabels: string[] = [];
  const unresolvedTokens: string[] = [];
  const seenDocIds = new Set<number>();
  let cleanedQuestion = question;

  for (const mention of uniqueMentions(knownMentions).sort((a, b) => b.label.length - a.label.length)) {
    const pattern = new RegExp(`(^|\\s)@${escapeRegExp(mention.label)}(?=\\s|$)`, "g");
    let matched = false;
    cleanedQuestion = cleanedQuestion.replace(pattern, (_value, prefix: string) => {
      matched = true;
      return prefix;
    });
    if (!matched || seenDocIds.has(mention.docId)) {
      continue;
    }
    seenDocIds.add(mention.docId);
    docIds.push(mention.docId);
    docLabels.push(mention.label);
  }

  cleanedQuestion = cleanedQuestion.replace(/(^|\s)@([^\s@]+)/g, (full, prefix: string, token: string) => {
    const byId = token.match(/^#?(\d+)$/);
    const matchedDoc = byId
      ? docs.find((doc) => doc.id === Number(byId[1]))
      : docs.find((doc) => normalizeText(doc.filename) === normalizeText(token));

    if (!matchedDoc) {
      unresolvedTokens.push(token);
      return full;
    }

    if (!seenDocIds.has(matchedDoc.id)) {
      seenDocIds.add(matchedDoc.id);
      docIds.push(matchedDoc.id);
      docLabels.push(matchedDoc.filename);
    }
    return prefix;
  });

  cleanedQuestion = cleanedQuestion.replace(/\s{2,}/g, " ").trim();
  return { cleanedQuestion, docIds, docLabels, unresolvedTokens };
}

/**
 * 渲染问答面板，并支持通过 @ 文档名引用多个文档。
 */
export function QaPanel({
  mentionSeed,
  activeModelId,
  activeModelLabel,
  onOpenCitation,
}: QaPanelProps) {
  const [question, setQuestion] = useState("");
  const [selectedCitationIdx, setSelectedCitationIdx] = useState<number | null>(null);
  const [selectedSuggestionIdx, setSelectedSuggestionIdx] = useState(0);
  const [knownMentions, setKnownMentions] = useState<KnownMention[]>([]);
  const [cursorPos, setCursorPos] = useState(0);
  const [lastAppliedSeed, setLastAppliedSeed] = useState<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const ask = useAskQuestion();
  const { data: docs = [] } = useDocuments();

  const activeMention = useMemo(() => getActiveMention(question, cursorPos), [question, cursorPos]);
  const parsedMentions = useMemo(
    () => parseMentionReferences(question, knownMentions, docs),
    [question, knownMentions, docs],
  );

  const suggestions = useMemo(() => {
    if (!activeMention) {
      return [];
    }

    const query = normalizeText(activeMention.query.replace(/^#/, ""));
    const referencedDocIds = new Set(parsedMentions.docIds);
    return docs
      .filter((doc) => !referencedDocIds.has(doc.id))
      .filter((doc) => {
        if (!query) {
          return true;
        }
        return (
          normalizeText(doc.filename).includes(query) ||
          String(doc.id).includes(query)
        );
      })
      .slice(0, 8);
  }, [activeMention, docs, parsedMentions.docIds]);

  const showSuggestions = Boolean(activeMention) && suggestions.length > 0;

  const focusTextarea = (nextCursor: number) => {
    requestAnimationFrame(() => {
      if (!textareaRef.current) {
        return;
      }
      textareaRef.current.focus();
      textareaRef.current.setSelectionRange(nextCursor, nextCursor);
      setCursorPos(nextCursor);
    });
  };

  const rememberMention = (doc: Pick<DocumentRecord, "id" | "filename">) => {
    setKnownMentions((prev) => {
      if (prev.some((item) => item.docId === doc.id)) {
        return prev;
      }
      return [...prev, { docId: doc.id, label: doc.filename }];
    });
  };

  const insertMentionAtCursor = (doc: Pick<DocumentRecord, "id" | "filename">) => {
    const token = `@${doc.filename} `;
    const textarea = textareaRef.current;
    const selectionStart = textarea?.selectionStart ?? question.length;
    const selectionEnd = textarea?.selectionEnd ?? question.length;
    const mention = getActiveMention(question, selectionStart);

    const replaceStart = mention ? mention.start : selectionStart;
    const replaceEnd = mention ? mention.end : selectionEnd;
    const needsLeadingSpace = replaceStart > 0 && !/\s/.test(question[replaceStart - 1] ?? "");
    const nextQuestion = [
      question.slice(0, replaceStart),
      needsLeadingSpace ? " " : "",
      token,
      question.slice(replaceEnd),
    ].join("");

    const nextCursor = question.slice(0, replaceStart).length + (needsLeadingSpace ? 1 : 0) + token.length;
    setQuestion(nextQuestion);
    rememberMention(doc);
    focusTextarea(nextCursor);
  };

  useEffect(() => {
    if (!mentionSeed || mentionSeed.nonce === lastAppliedSeed) {
      return;
    }

    requestAnimationFrame(() => {
      const token = `@${mentionSeed.docName}`;
      const mentionPattern = new RegExp(`(^|\\s)${escapeRegExp(token)}(?=\\s|$)`);
      setQuestion((prev) => {
        if (mentionPattern.test(prev)) {
          return prev;
        }
        const prefix = prev.trimEnd();
        const nextQuestion = prefix ? `${prefix} ${token} ` : `${token} `;
        focusTextarea(nextQuestion.length);
        return nextQuestion;
      });
      setKnownMentions((prev) => {
        if (prev.some((item) => item.docId === mentionSeed.docId)) {
          return prev;
        }
        return [...prev, { docId: mentionSeed.docId, label: mentionSeed.docName }];
      });
      setLastAppliedSeed(mentionSeed.nonce);
    });
  }, [lastAppliedSeed, mentionSeed]);

  const handleAsk = async () => {
    if (!question.trim()) {
      toast.error("请输入问题");
      return;
    }
    if (parsedMentions.unresolvedTokens.length > 0) {
      toast.error(`未找到引用文档: ${parsedMentions.unresolvedTokens[0]}`);
      return;
    }
    if (!parsedMentions.cleanedQuestion) {
      toast.error("请输入有效问题内容");
      return;
    }

    setSelectedCitationIdx(null);
    try {
      await ask.mutateAsync({
        question: parsedMentions.cleanedQuestion,
        doc_ids: parsedMentions.docIds.length > 0 ? parsedMentions.docIds : undefined,
        top_k: 5,
        llm_model: activeModelId ?? undefined,
      });
    } catch {
      toast.error("问答失败");
    }
  };

  return (
    <div className="flex h-full flex-col">
      <ScrollArea className="min-h-0 flex-1 px-4 py-3">
        {ask.isPending && (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
            <span className="mt-2 text-sm">思考中...</span>
          </div>
        )}

        {ask.data && !ask.isPending && (
          <div className="space-y-4">
            <Card>
              <CardContent className="pt-4">
                <div className="mb-3 flex items-center justify-between">
                  <h4 className="font-semibold">回答</h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => {
                      navigator.clipboard.writeText(ask.data!.answer);
                      toast.success("已复制");
                    }}
                  >
                    <Copy className="mr-1 h-3 w-3" />
                    复制
                  </Button>
                </div>
                <div className="whitespace-pre-wrap text-sm leading-7 text-muted-foreground">
                  {ask.data.answer}
                </div>
              </CardContent>
            </Card>

            {ask.data.citations.length > 0 && (
              <div>
                <h4 className="mb-2 text-sm font-semibold text-muted-foreground">
                  引用 ({ask.data.citations.length})
                </h4>
                <div className="space-y-2">
                  {ask.data.citations.map((citation: CitationItem, idx: number) => (
                    <CitationCard
                      key={idx}
                      citation={citation}
                      index={idx + 1}
                      selected={selectedCitationIdx === idx}
                      onClick={() => {
                        setSelectedCitationIdx(idx);
                        onOpenCitation(citation);
                      }}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {!ask.data && !ask.isPending && (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <FileText className="h-12 w-12 opacity-20" />
            <p className="mt-3 text-sm">输入问题，可用 `@` 引用多个文档</p>
          </div>
        )}
      </ScrollArea>

      <Separator />

      <div className="space-y-2 p-4">
        <div className="rounded-md border bg-muted/40 px-3 py-2 text-xs">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">当前文本模型</p>
              <p className="mt-1 truncate font-medium text-foreground">
                {activeModelLabel ?? "默认模型"}
              </p>
            </div>
            <div className="min-w-0 text-right text-muted-foreground">
              <p className="text-[10px] uppercase tracking-wide">检索范围</p>
              <p className="mt-1 truncate font-medium text-foreground">
                {parsedMentions.docLabels.length > 0
                  ? `已引用 ${parsedMentions.docLabels.length} 篇文档`
                  : "全库检索"}
              </p>
            </div>
          </div>
          {parsedMentions.docLabels.length > 0 && (
            <p className="mt-2 truncate text-[11px] text-muted-foreground">
              {parsedMentions.docLabels.join(" / ")}
            </p>
          )}
        </div>

        <div className="relative">
          <Textarea
            ref={textareaRef}
            placeholder="输入问题，使用 @ 引用文档..."
            value={question}
            onChange={(e: ChangeEvent<HTMLTextAreaElement>) => {
              setQuestion(e.target.value);
              setCursorPos(e.target.selectionStart ?? e.target.value.length);
              setSelectedSuggestionIdx(0);
            }}
            onSelect={(e) => {
              setCursorPos(e.currentTarget.selectionStart ?? e.currentTarget.value.length);
            }}
            onKeyUp={(e) => {
              setCursorPos(e.currentTarget.selectionStart ?? e.currentTarget.value.length);
            }}
            onKeyDown={(e: KeyboardEvent<HTMLTextAreaElement>) => {
              if (showSuggestions && e.key === "ArrowDown") {
                e.preventDefault();
                setSelectedSuggestionIdx((idx) => (idx + 1) % suggestions.length);
                return;
              }
              if (showSuggestions && e.key === "ArrowUp") {
                e.preventDefault();
                setSelectedSuggestionIdx((idx) => (idx - 1 + suggestions.length) % suggestions.length);
                return;
              }
              if (showSuggestions && e.key === "Enter" && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                insertMentionAtCursor(suggestions[Math.min(selectedSuggestionIdx, suggestions.length - 1)] ?? suggestions[0]);
                return;
              }
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                handleAsk();
              }
            }}
            className="min-h-[92px] resize-none text-sm"
          />

          {showSuggestions && (
            <div className="absolute inset-x-0 bottom-full z-10 mb-2 overflow-hidden rounded-lg border bg-background shadow-lg">
              <div className="border-b px-3 py-2 text-[11px] text-muted-foreground">
                选择文档后将插入 `@文档名`
              </div>
              <div className="max-h-64 overflow-y-auto p-1">
                {suggestions.map((doc, idx) => (
                  <button
                    key={doc.id}
                    type="button"
                    className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition ${
                      idx === selectedSuggestionIdx ? "bg-muted" : "hover:bg-muted/60"
                    }`}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      insertMentionAtCursor(doc);
                    }}
                  >
                    <div className="min-w-0">
                      <div className="truncate font-medium text-foreground">{doc.filename}</div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        #{doc.id} · {doc.doc_type || "unknown"}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <Button
            onClick={handleAsk}
            disabled={ask.isPending || !question.trim()}
            className="flex-1"
          >
            {ask.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            开始问答
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              setQuestion("");
              setKnownMentions([]);
            }}
            className="px-4"
          >
            清空
          </Button>
        </div>
        <p className="text-xs text-muted-foreground/60">输入 `@` 引用文档；不引用时默认全库检索。Ctrl + Enter 提交</p>
      </div>
    </div>
  );
}

function CitationCard({
  citation,
  index,
  selected,
  onClick,
}: {
  citation: CitationItem;
  index: number;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full rounded-lg border p-3 text-left transition ${
        selected
          ? "border-primary bg-primary/10 ring-1 ring-primary/20"
          : "border-border hover:border-primary/50 hover:bg-muted/50"
      }`}
    >
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
            selected ? "bg-primary text-primary-foreground" : "bg-primary/10 text-primary"
          }`}>
            {index}
          </span>
          <span className="truncate text-xs font-medium">
            {`文档 ${citation.doc_id}`}
          </span>
        </div>
        <span className="shrink-0 text-xs text-muted-foreground">
          {(citation.score).toFixed(3)}
        </span>
      </div>
      {citation.title_path && (
        <p className="mb-1 truncate text-[11px] text-muted-foreground/60">
          {citation.title_path}
        </p>
      )}
      <p className="line-clamp-2 text-xs text-muted-foreground">
        {citation.snippet}
      </p>
    </button>
  );
}
