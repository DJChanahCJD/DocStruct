import { useState, useRef, useEffect } from "react";
import { Wand2, Loader2, Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useReExtract } from "@/hooks/use-api";
import { toast } from "sonner";

type FieldState = "idle" | "inputting" | "loading" | "reviewing";

interface FieldInlineEditorProps {
  fieldKey: string;
  fieldValue: unknown;
  docId: number;
  /** 用户确认新值后的回调，父组件负责合并和持久化 */
  onApply: (fieldKey: string, newValue: unknown) => void;
}

/** 将任意值格式化为简短预览字符串 */
function formatPreview(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "string") return value.length > 80 ? value.slice(0, 80) + "…" : value;
  const str = JSON.stringify(value);
  return str.length > 100 ? str.slice(0, 100) + "…" : str;
}

/**
 * 单个顶层字段的行级追问编辑器。
 * 状态机：idle → inputting → loading → reviewing → idle
 */
export function FieldInlineEditor({
  fieldKey,
  fieldValue,
  docId,
  onApply,
}: FieldInlineEditorProps) {
  const [fieldState, setFieldState] = useState<FieldState>("idle");
  const [instruction, setInstruction] = useState("");
  const [newValue, setNewValue] = useState<unknown>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const reExtract = useReExtract(docId);

  // 进入输入状态时自动聚焦
  useEffect(() => {
    if (fieldState === "inputting") {
      textareaRef.current?.focus();
    }
  }, [fieldState]);

  function handleOpenInput() {
    setInstruction("");
    setFieldState("inputting");
  }

  function handleCancel() {
    setInstruction("");
    setNewValue(null);
    setFieldState("idle");
  }

  async function handleSubmit() {
    if (!instruction.trim()) {
      handleCancel();
      return;
    }
    setFieldState("loading");
    try {
      const resp = await reExtract.mutateAsync({
        scope: "field",
        field_key: fieldKey,
        instruction: instruction.trim(),
      });
      const extracted = resp.result[fieldKey];
      setNewValue(extracted);
      setFieldState("reviewing");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`字段「${fieldKey}」提取失败: ${msg}`);
      setFieldState("inputting");
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === "Escape") {
      handleCancel();
    }
  }

  function handleApply() {
    onApply(fieldKey, newValue);
    setInstruction("");
    setNewValue(null);
    setFieldState("idle");
  }

  const keyLabel = (
    <span className="text-blue-400 font-medium font-mono mr-1">"{fieldKey}":</span>
  );

  // --- idle 状态：正常展示值，悬停显示魔法棒 ---
  if (fieldState === "idle") {
    return (
      <div className="group flex items-start gap-1 py-0.5 rounded hover:bg-muted/40 transition-colors">
        <div className="flex-1 min-w-0 font-mono text-sm leading-relaxed">
          {keyLabel}
          <span className="text-muted-foreground break-all">{formatPreview(fieldValue)}</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-primary"
          onClick={handleOpenInput}
          title="追问修改此字段"
        >
          <Wand2 className="h-3 w-3" />
        </Button>
      </div>
    );
  }

  // --- inputting 状态：展开输入框 ---
  if (fieldState === "inputting") {
    return (
      <div className="py-1 space-y-1.5 rounded border border-border/60 bg-muted/30 px-2">
        <div className="font-mono text-sm text-blue-400 font-medium">"{fieldKey}"</div>
        <Textarea
          ref={textareaRef}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="描述你的修改意图… (Enter 提交，Shift+Enter 换行，Esc 取消)"
          className="min-h-[60px] text-sm resize-none bg-background"
          rows={2}
        />
        <div className="flex gap-1.5 justify-end">
          <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={handleCancel}>
            取消
          </Button>
          <Button size="sm" className="h-6 text-xs" onClick={handleSubmit}>
            提取
          </Button>
        </div>
      </div>
    );
  }

  // --- loading 状态：旋转图标 ---
  if (fieldState === "loading") {
    return (
      <div className="flex items-center gap-2 py-1 px-2 rounded bg-muted/30">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
        <span className="font-mono text-sm text-blue-400 font-medium">"{fieldKey}"</span>
        <span className="text-xs text-muted-foreground">提取中…</span>
      </div>
    );
  }

  // --- reviewing 状态：旧值/新值 diff ---
  return (
    <div className="py-1 space-y-1.5 rounded border border-border/60 bg-muted/20 px-2">
      <div className="font-mono text-sm text-blue-400 font-medium">"{fieldKey}"</div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="space-y-0.5">
          <div className="text-muted-foreground font-medium">旧值</div>
          <div className="font-mono text-red-400/80 line-through break-all bg-red-50/10 rounded px-1.5 py-1">
            {formatPreview(fieldValue)}
          </div>
        </div>
        <div className="space-y-0.5">
          <div className="text-muted-foreground font-medium">新值</div>
          <div className="font-mono text-green-400 break-all bg-green-50/10 rounded px-1.5 py-1">
            {formatPreview(newValue)}
          </div>
        </div>
      </div>
      <div className="flex gap-1.5 justify-end">
        <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={handleCancel}>
          <X className="h-3 w-3 mr-1" />放弃
        </Button>
        <Button size="sm" className="h-6 text-xs" onClick={handleApply}>
          <Check className="h-3 w-3 mr-1" />应用
        </Button>
      </div>
    </div>
  );
}
