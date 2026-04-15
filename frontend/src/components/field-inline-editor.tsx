import { useState, useRef, useEffect } from "react";
import { Wand2, Pencil, Loader2, Check, X } from "lucide-react";
import { diffLines } from "diff";
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

type DiffLineType = "unchanged" | "removed" | "added" | "placeholder";

interface DiffLineItem {
  type: DiffLineType;
  content: string;
}

interface FieldInlineEditorProps {
  fieldKey: string;
  fieldValue: unknown;
  docId: number;
  /** 用户确认新值后的回调，父组件负责合并和持久化 */
  onApply: (fieldKey: string, newValue: unknown) => Promise<void>;
}

/** 将任意值格式化为压缩预览字符串 */
function formatPreview(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
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

function splitDiffChunk(value: string): string[] {
  if (value === "") return [""];
  const lines = value.split("\n");
  if (lines.length > 1 && lines[lines.length - 1] === "") {
    lines.pop();
  }
  return lines;
}

function toDiffLine(type: DiffLineType, content?: string): DiffLineItem {
  if (type === "placeholder") return { type, content: "\u00A0" };
  return { type, content: content === "" ? "\u00A0" : content ?? "\u00A0" };
}

function computeDiffLineItems(oldText: string, newText: string): {
  leftLines: DiffLineItem[];
  rightLines: DiffLineItem[];
} {
  const changes = diffLines(oldText, newText);
  const leftLines: DiffLineItem[] = [];
  const rightLines: DiffLineItem[] = [];
  let pendingRemoved: string[] = [];
  let pendingAdded: string[] = [];

  const flushPending = () => {
    if (pendingRemoved.length === 0 && pendingAdded.length === 0) return;
    const maxLength = Math.max(pendingRemoved.length, pendingAdded.length);
    for (let i = 0; i < maxLength; i += 1) {
      leftLines.push(
        pendingRemoved[i] !== undefined
          ? toDiffLine("removed", pendingRemoved[i])
          : toDiffLine("placeholder"),
      );
      rightLines.push(
        pendingAdded[i] !== undefined
          ? toDiffLine("added", pendingAdded[i])
          : toDiffLine("placeholder"),
      );
    }
    pendingRemoved = [];
    pendingAdded = [];
  };

  for (const change of changes) {
    const lines = splitDiffChunk(change.value);
    if (change.removed) {
      pendingRemoved.push(...lines);
      continue;
    }
    if (change.added) {
      pendingAdded.push(...lines);
      continue;
    }

    flushPending();
    for (const line of lines) {
      leftLines.push(toDiffLine("unchanged", line));
      rightLines.push(toDiffLine("unchanged", line));
    }
  }

  flushPending();
  return { leftLines, rightLines };
}

function getDiffLineClass(type: DiffLineType): string {
  switch (type) {
    case "removed":
      return "bg-red-500/15 text-red-500";
    case "added":
      return "bg-green-500/15 text-green-500";
    case "placeholder":
      return "select-none text-transparent";
    default:
      return "text-muted-foreground";
  }
}

/**
 * 单个顶层字段的行级编辑器，支持两种操作模式：
 * - 直接编辑（Pencil）：inline 编辑值文本，无变化时跳过 reviewing 直接提示
 * - 追问提取（Wand2）：输入自然语言指令，LLM 重新提取，预览 diff 后应用
 *
 * idle 状态默认显示压缩值；
 * inputting 状态上方内联展示完整当前值供参考。
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
  const leftDiffRef = useRef<HTMLDivElement>(null);
  const rightDiffRef = useRef<HTMLDivElement>(null);
  const isSyncingScrollRef = useRef(false);
  const reExtract = useReExtract(docId);

  useEffect(() => {
    if (fieldState === "editing") editRef.current?.focus();
    if (fieldState === "inputting") instructionRef.current?.focus();
  }, [fieldState]);

  useEffect(() => {
    if (fieldState !== "reviewing") return;

    const left = leftDiffRef.current;
    const right = rightDiffRef.current;
    if (!left || !right) return;

    const syncScroll = (source: HTMLDivElement, target: HTMLDivElement) => {
      if (isSyncingScrollRef.current) return;
      isSyncingScrollRef.current = true;
      target.scrollTop = source.scrollTop;
      target.scrollLeft = source.scrollLeft;
      requestAnimationFrame(() => {
        isSyncingScrollRef.current = false;
      });
    };

    const handleLeftScroll = () => syncScroll(left, right);
    const handleRightScroll = () => syncScroll(right, left);

    left.addEventListener("scroll", handleLeftScroll);
    right.addEventListener("scroll", handleRightScroll);

    return () => {
      left.removeEventListener("scroll", handleLeftScroll);
      right.removeEventListener("scroll", handleRightScroll);
      isSyncingScrollRef.current = false;
    };
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
      try {
        JSON.parse(text);
        setEditError(null);
      } catch (e) {
        setEditError((e as Error).message);
      }
    } else {
      setEditError(null);
    }
  }

  async function handleEditSave() {
    if (editError) return;
    const parsed = editTextToValue(editText, fieldValue);
    // 值未变化时跳过 reviewing，直接提示并回到 idle
    if (JSON.stringify(parsed) === JSON.stringify(fieldValue)) {
      handleCancel();
      toast.info(`字段「${fieldKey}」无变化`);
      return;
    }
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
      setNewValue(resp.result[fieldKey]);
      setFieldState("reviewing");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`字段「${fieldKey}」提取失败: ${msg}`);
      setFieldState("inputting");
    }
  }

  function handleInstructionKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === "Escape") {
      handleCancel();
    }
  }

  // ── 公共操作 ────────────────────────────────────────────────────────────

  function handleCancel() {
    setEditText("");
    setEditError(null);
    setInstruction("");
    setNewValue(null);
    setFieldState("idle");
  }

  async function handleApply() {
    try {
      await onApply(fieldKey, newValue);
    } finally {
      setEditText("");
      setEditError(null);
      setInstruction("");
      setNewValue(null);
      setFieldState("idle");
    }
  }

  // ── 渲染 ──────────────────────────────────────────────────────────────

  const keyLabel = (
    <span className="mr-1 shrink-0 font-mono font-medium text-blue-400">"{fieldKey}":</span>
  );

  const previewText = formatPreview(fieldValue);
  const fullText = valueToEditText(fieldValue);

  // idle：默认显示压缩值，悬停显示双图标
  if (fieldState === "idle") {
    return (
      <div className="group flex items-start gap-1 rounded py-0.5 transition-colors hover:bg-muted/40">
        <div className="min-w-0 flex-1 font-mono text-sm leading-relaxed">
          {keyLabel}
          <span className="break-all text-muted-foreground">{previewText}</span>
        </div>
        <div className="flex shrink-0 gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 text-muted-foreground hover:text-foreground"
            onClick={handleOpenEdit}
            title="直接编辑此字段"
          >
            <Pencil className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 text-muted-foreground hover:text-primary"
            onClick={handleOpenInput}
            title="追问 LLM 修改此字段"
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
      <div className="space-y-1.5 rounded border border-border/60 bg-muted/30 px-2 py-1">
        <div className="flex items-center gap-1.5">
          <Pencil className="h-3 w-3 text-muted-foreground" />
          <span className="font-mono text-sm font-medium text-blue-400">"{fieldKey}"</span>
        </div>
        <Textarea
          ref={editRef}
          value={editText}
          onChange={(e) => handleEditChange(e.target.value)}
          onKeyDown={handleEditKeyDown}
          className="min-h-[60px] resize-y bg-background font-mono text-sm"
          rows={typeof fieldValue === "object" ? 4 : 2}
          spellCheck={false}
        />
        {editError && <p className="text-xs text-destructive">{editError}</p>}
        <div className="flex justify-end gap-1.5">
          <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={handleCancel}>
            取消
          </Button>
          <Button size="sm" className="h-6 text-xs" onClick={handleEditSave} disabled={!!editError}>
            预览
          </Button>
        </div>
      </div>
    );
  }

  // inputting：追问指令输入（上方显示完整当前值供参考）
  if (fieldState === "inputting") {
    return (
      <div className="space-y-1.5 rounded border border-border/60 bg-muted/30 px-2 py-1">
        <div className="flex items-center gap-1.5">
          <Wand2 className="h-3 w-3 text-primary" />
          <span className="font-mono text-sm font-medium text-blue-400">"{fieldKey}"</span>
        </div>
        <div className="rounded border border-border/40 bg-muted/60 px-2 py-1.5">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground/60">当前值</div>
          <div className="break-all whitespace-pre-wrap font-mono text-xs leading-relaxed text-muted-foreground">
            {fullText}
          </div>
        </div>
        <Textarea
          ref={instructionRef}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={handleInstructionKeyDown}
          placeholder="描述修改意图… (Enter 提交，Shift+Enter 换行，Esc 取消)"
          className="min-h-[60px] resize-none bg-background text-sm"
          rows={2}
        />
        <div className="flex justify-end gap-1.5">
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

  // loading：提取中
  if (fieldState === "loading") {
    return (
      <div className="flex items-center gap-2 rounded bg-muted/30 px-2 py-1">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
        <span className="font-mono text-sm font-medium text-blue-400">"{fieldKey}"</span>
        <span className="text-xs text-muted-foreground">提取中…</span>
      </div>
    );
  }

  const { leftLines, rightLines } = computeDiffLineItems(fullText, valueToEditText(newValue));

  // reviewing：旧值/新值 diff（编辑和追问共用）
  return (
    <div className="space-y-1.5 rounded border border-border/60 bg-muted/20 px-2 py-1">
      <span className="font-mono text-sm font-medium text-blue-400">"{fieldKey}"</span>
      <div className="grid grid-cols-1 gap-2 text-xs lg:grid-cols-2">
        <div className="space-y-0.5">
          <div className="text-muted-foreground font-medium">旧值</div>
          <div
            ref={leftDiffRef}
            className="max-h-64 overflow-auto rounded border border-border/40 bg-background/40 font-mono text-[11px] leading-relaxed"
          >
            {leftLines.map((line, index) => (
              <div
                key={`left-${index}`}
                className={`min-h-[20px] whitespace-pre-wrap px-2 py-0.5 ${getDiffLineClass(line.type)}`}
              >
                {line.content}
              </div>
            ))}
          </div>
        </div>
        <div className="space-y-0.5">
          <div className="text-muted-foreground font-medium">新值</div>
          <div
            ref={rightDiffRef}
            className="max-h-64 overflow-auto rounded border border-border/40 bg-background/40 font-mono text-[11px] leading-relaxed"
          >
            {rightLines.map((line, index) => (
              <div
                key={`right-${index}`}
                className={`min-h-[20px] whitespace-pre-wrap px-2 py-0.5 ${getDiffLineClass(line.type)}`}
              >
                {line.content}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="flex justify-end gap-1.5">
        <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={handleCancel}>
          <X className="mr-1 h-3 w-3" />放弃
        </Button>
        <Button size="sm" className="h-6 text-xs" onClick={handleApply}>
          <Check className="mr-1 h-3 w-3" />应用
        </Button>
      </div>
    </div>
  );
}
