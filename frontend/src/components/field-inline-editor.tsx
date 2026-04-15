import { useState, useRef, useEffect } from "react";
import { Wand2, Pencil, Loader2, Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useReExtract } from "@/hooks/use-api";
import { toast } from "sonner";

/**
 * 状态机：
 *   idle → editing   (Pencil: 直接编辑值)
 *   idle → inputting (Wand2: 追问 LLM 提取)
 *   editing   → saving   → idle
 *   inputting → loading  → reviewing → idle
 */
type FieldState = "idle" | "editing" | "saving" | "inputting" | "loading" | "reviewing";

interface FieldInlineEditorProps {
  fieldKey: string;
  fieldValue: unknown;
  docId: number;
  /** 用户确认新值后的回调，父组件负责合并和持久化 */
  onApply: (fieldKey: string, newValue: unknown) => Promise<void>;
}

/** 将任意值格式化为简短预览字符串 */
function formatPreview(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "string") return value.length > 80 ? value.slice(0, 80) + "…" : value;
  const str = JSON.stringify(value);
  return str.length > 100 ? str.slice(0, 100) + "…" : str;
}

/** 将值序列化为可编辑的字符串 */
function valueToEditText(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

/** 将编辑字符串反序列化回原始值（尝试 JSON parse，失败则保留字符串） */
function editTextToValue(text: string, originalValue: unknown): unknown {
  if (typeof originalValue === "string") return text;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/**
 * 单个顶层字段的行级编辑器，支持两种操作模式：
 * - 直接编辑（Pencil）：inline 编辑值文本，保存前预览 diff
 * - 追问提取（Wand2）：输入自然语言指令，LLM 重新提取，预览 diff 后应用
 */
export function FieldInlineEditor({
  fieldKey,
  fieldValue,
  docId,
  onApply,
}: FieldInlineEditorProps) {
  const [fieldState, setFieldState] = useState<FieldState>("idle");
  // editing 模式
  const [editText, setEditText] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  // inputting 模式
  const [instruction, setInstruction] = useState("");
  // reviewing 阶段（两种模式共用）
  const [newValue, setNewValue] = useState<unknown>(null);

  const editRef = useRef<HTMLTextAreaElement>(null);
  const instructionRef = useRef<HTMLTextAreaElement>(null);
  const reExtract = useReExtract(docId);

  useEffect(() => {
    if (fieldState === "editing") editRef.current?.focus();
    if (fieldState === "inputting") instructionRef.current?.focus();
  }, [fieldState]);

  // ── 直接编辑分支 ─────────────────────────────────────────────────────────

  function handleOpenEdit() {
    setEditText(valueToEditText(fieldValue));
    setEditError(null);
    setFieldState("editing");
  }

  function handleEditChange(text: string) {
    setEditText(text);
    if (typeof fieldValue !== "string") {
      try { JSON.parse(text); setEditError(null); }
      catch (e) { setEditError((e as Error).message); }
    } else {
      setEditError(null);
    }
  }

  async function handleEditSave() {
    if (editError) return;
    const parsed = editTextToValue(editText, fieldValue);
    setNewValue(parsed);
    setFieldState("reviewing");
  }

  function handleEditKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && typeof fieldValue !== "object") {
      e.preventDefault();
      handleEditSave();
    } else if (e.key === "Escape") {
      handleCancel();
    }
  }

  // ── 追问提取分支 ─────────────────────────────────────────────────────────

  function handleOpenInput() {
    setInstruction("");
    setFieldState("inputting");
  }

  async function handleSubmit() {
    if (!instruction.trim()) { handleCancel(); return; }
    setFieldState("loading");
    try {
      const resp = await reExtract.mutateAsync({
        scope: "field",
        field_key: fieldKey,
        instruction: instruction.trim(),
      });
      setNewValue(resp.result[fieldKey]);
      setFieldState("reviewing");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`字段「${fieldKey}」提取失败: ${msg}`);
      setFieldState("inputting");
    }
  }

  function handleInstructionKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
    else if (e.key === "Escape") { handleCancel(); }
  }

  // ── 公共操作 ────────────────────────────────────────────────────────────

  function handleCancel() {
    setEditText(""); setEditError(null);
    setInstruction(""); setNewValue(null);
    setFieldState("idle");
  }

  async function handleApply() {
    try {
      await onApply(fieldKey, newValue);
    } finally {
      setEditText(""); setEditError(null);
      setInstruction(""); setNewValue(null);
      setFieldState("idle");
    }
  }

  // ── 渲染 ──────────────────────────────────────────────────────────────

  const keyLabel = (
    <span className="font-mono text-blue-400 font-medium mr-1 shrink-0">"{fieldKey}":</span>
  );

  // idle：悬停显示双图标
  if (fieldState === "idle") {
    return (
      <div className="group flex items-start gap-1 py-0.5 rounded hover:bg-muted/40 transition-colors">
        <div className="flex-1 min-w-0 font-mono text-sm leading-relaxed">
          {keyLabel}
          <span className="text-muted-foreground break-all">{formatPreview(fieldValue)}</span>
        </div>
        <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
          <Button
            variant="ghost" size="icon"
            className="h-5 w-5 text-muted-foreground hover:text-foreground"
            onClick={handleOpenEdit} title="直接编辑此字段"
          >
            <Pencil className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost" size="icon"
            className="h-5 w-5 text-muted-foreground hover:text-primary"
            onClick={handleOpenInput} title="追问 LLM 修改此字段"
          >
            <Wand2 className="h-3 w-3" />
          </Button>
        </div>
      </div>
    );
  }

  // editing：inline 编辑值
  if (fieldState === "editing") {
    return (
      <div className="py-1 space-y-1.5 rounded border border-border/60 bg-muted/30 px-2">
        <div className="flex items-center gap-1.5">
          <Pencil className="h-3 w-3 text-muted-foreground" />
          <span className="font-mono text-sm text-blue-400 font-medium">"{fieldKey}"</span>
        </div>
        <Textarea
          ref={editRef}
          value={editText}
          onChange={(e) => handleEditChange(e.target.value)}
          onKeyDown={handleEditKeyDown}
          className="min-h-[60px] text-sm font-mono resize-y bg-background"
          rows={typeof fieldValue === "object" ? 4 : 2}
          spellCheck={false}
        />
        {editError && (
          <p className="text-xs text-destructive">{editError}</p>
        )}
        <div className="flex gap-1.5 justify-end">
          <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={handleCancel}>取消</Button>
          <Button size="sm" className="h-6 text-xs" onClick={handleEditSave} disabled={!!editError}>
            预览
          </Button>
        </div>
      </div>
    );
  }

  // inputting：追问指令输入
  if (fieldState === "inputting") {
    return (
      <div className="py-1 space-y-1.5 rounded border border-border/60 bg-muted/30 px-2">
        <div className="flex items-center gap-1.5">
          <Wand2 className="h-3 w-3 text-primary" />
          <span className="font-mono text-sm text-blue-400 font-medium">"{fieldKey}"</span>
        </div>
        <Textarea
          ref={instructionRef}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={handleInstructionKeyDown}
          placeholder="描述修改意图… (Enter 提交，Shift+Enter 换行，Esc 取消)"
          className="min-h-[60px] text-sm resize-none bg-background"
          rows={2}
        />
        <div className="flex gap-1.5 justify-end">
          <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={handleCancel}>取消</Button>
          <Button size="sm" className="h-6 text-xs" onClick={handleSubmit}>提取</Button>
        </div>
      </div>
    );
  }

  // loading：提取中
  if (fieldState === "loading") {
    return (
      <div className="flex items-center gap-2 py-1 px-2 rounded bg-muted/30">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
        <span className="font-mono text-sm text-blue-400 font-medium">"{fieldKey}"</span>
        <span className="text-xs text-muted-foreground">提取中…</span>
      </div>
    );
  }

  // reviewing：旧值/新值 diff（编辑和追问共用）
  return (
    <div className="py-1 space-y-1.5 rounded border border-border/60 bg-muted/20 px-2">
      <span className="font-mono text-sm text-blue-400 font-medium">"{fieldKey}"</span>
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
