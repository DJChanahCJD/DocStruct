import { useState } from "react";
import type { ChangeEvent, KeyboardEvent } from "react";
import { Copy, FileText, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useAskQuestion } from "@/hooks/use-api";
import type { CitationItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";

interface QaPanelProps {
  selectedDocId: number | null;
  activeModelId?: string | null;
  activeModelLabel?: string;
  onOpenCitation: (citation: CitationItem) => void;
}

/**
 * 渲染问答面板，并复用全局文本模型发起问答。
 */
export function QaPanel({
  selectedDocId,
  activeModelId,
  activeModelLabel,
  onOpenCitation,
}: QaPanelProps) {
  const [question, setQuestion] = useState("");
  const [selectedCitationIdx, setSelectedCitationIdx] = useState<number | null>(null);
  const ask = useAskQuestion();

  const handleAsk = async () => {
    if (!question.trim()) {
      toast.error("请输入问题");
      return;
    }
    setSelectedCitationIdx(null);
    try {
      await ask.mutateAsync({
        question: question.trim(),
        doc_id: selectedDocId,
        top_k: 5,
        llm_model: activeModelId ?? undefined,
      });
    } catch {
      toast.error("问答失败");
    }
  };

  return (
    <div className="flex h-full flex-col">
      <ScrollArea className="flex-1 min-h-0 px-4 py-3">
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
            <p className="mt-3 text-sm">选择文档或全库模式提问</p>
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
            <div className="text-right text-muted-foreground">
              <p className="text-[10px] uppercase tracking-wide">检索范围</p>
              <p className="mt-1 font-medium text-foreground">
                {selectedDocId ? `文档 #${selectedDocId}` : "全库检索"}
              </p>
            </div>
          </div>
        </div>

        <Textarea
          placeholder="输入问题..."
          value={question}
          onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setQuestion(e.target.value)}
          onKeyDown={(e: KeyboardEvent<HTMLTextAreaElement>) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              handleAsk();
            }
          }}
          className="min-h-[80px] resize-none text-sm"
        />
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
            }}
            className="px-4"
          >
            清空
          </Button>
        </div>
        <p className="text-xs text-muted-foreground/60">Ctrl + Enter 快捷提交</p>
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
