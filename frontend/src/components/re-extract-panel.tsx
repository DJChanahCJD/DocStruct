import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, X, Check, AlertCircle, RefreshCw } from "lucide-react";
import { useReExtract } from "@/hooks/use-api";
import { toast } from "sonner";

// ─── Types ────────────────────────────────────────────────────────────────────

type DiffStatus = "added" | "removed" | "modified" | "unchanged";
type PanelState = "configuring" | "extracting" | "reviewing";

interface ReExtractPanelProps {
  docId: number;
  currentData: Record<string, unknown>;
  onApply: (newData: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}

// ─── Diff 计算（顶层 key 级别）────────────────────────────────────────────────

function computeDiff(
  oldData: Record<string, unknown>,
  newData: Record<string, unknown>,
  fieldKey?: string | null,
): Record<string, DiffStatus> {
  const result: Record<string, DiffStatus> = {};
  const keys = new Set([
    ...(fieldKey ? [fieldKey] : Object.keys(oldData)),
    ...(fieldKey ? [fieldKey] : Object.keys(newData)),
  ]);
  for (const k of keys) {
    const inOld = k in oldData;
    const inNew = k in newData;
    if (!inOld) result[k] = "added";
    else if (!inNew) result[k] = "removed";
    else if (JSON.stringify(oldData[k]) !== JSON.stringify(newData[k])) result[k] = "modified";
    else result[k] = "unchanged";
  }
  return result;
}

const DIFF_COLORS: Record<DiffStatus, string> = {
  added: "bg-green-50 border-l-4 border-green-400 dark:bg-green-950/30",
  removed: "bg-red-50 border-l-4 border-red-400 dark:bg-red-950/30",
  modified: "bg-yellow-50 border-l-4 border-yellow-400 dark:bg-yellow-950/30",
  unchanged: "",
};

const DIFF_BADGE: Record<DiffStatus, string | null> = {
  added: "新增",
  removed: "已删除",
  modified: "已修改",
  unchanged: null,
};

// ─── Component ────────────────────────────────────────────────────────────────

export function ReExtractPanel({ docId, currentData, onApply, onCancel }: ReExtractPanelProps) {
  const reExtract = useReExtract(docId);

  const [panelState, setPanelState] = useState<PanelState>("configuring");
  const [scope, setScope] = useState<"full" | "field">("full");
  const [fieldKey, setFieldKey] = useState("");
  const [instruction, setInstruction] = useState("");
  const [error, setError] = useState<string | null>(null);

  // reviewing 阶段的结果
  const [previewData, setPreviewData] = useState<Record<string, unknown> | null>(null);
  const [diffScope, setDiffScope] = useState<"full" | "field">("full");
  const [diffFieldKey, setDiffFieldKey] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // 获取文档已有的顶层 key 列表，供字段选择
  const availableKeys = Object.keys(currentData);

  /** 执行提取 */
  const handleExecute = async () => {
    if (scope === "field" && !fieldKey.trim()) {
      setError("请输入或选择字段名");
      return;
    }
    setError(null);
    setPanelState("extracting");

    try {
      const resp = await reExtract.mutateAsync({
        scope,
        field_key: scope === "field" ? fieldKey.trim() : undefined,
        instruction: instruction.trim() || undefined,
      });
      setPreviewData(resp.result);
      setDiffScope(resp.scope);
      setDiffFieldKey(resp.field_key ?? null);
      setPanelState("reviewing");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "提取失败，请重试";
      setError(msg);
      setPanelState("configuring");
    }
  };

  /** 应用结果：field 模式 merge，full 模式整体覆盖 */
  const handleApply = async () => {
    if (!previewData) return;
    setIsSaving(true);
    try {
      const merged =
        diffScope === "field" && diffFieldKey
          ? { ...currentData, [diffFieldKey]: previewData[diffFieldKey] }
          : previewData;
      await onApply(merged);
      toast.success("已应用新提取结果");
    } catch {
      toast.error("保存失败");
    } finally {
      setIsSaving(false);
    }
  };

  // ── 配置面板 ──────────────────────────────────────────────────────────────

  if (panelState === "configuring") {
    return (
      <div className="flex flex-col gap-4 rounded-md border bg-muted/30 p-4">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-sm font-medium">
            <RefreshCw className="h-3.5 w-3.5" />
            重新提取
          </span>
          <Button size="sm" variant="ghost" className="h-7 px-2" onClick={onCancel}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>

        {/* 范围选择 */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-muted-foreground">提取范围</label>
          <div className="flex gap-2">
            <button
              onClick={() => setScope("full")}
              className={`rounded-md border px-3 py-1.5 text-xs transition-colors ${
                scope === "full"
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-background hover:bg-muted"
              }`}
            >
              全量提取
            </button>
            <button
              onClick={() => setScope("field")}
              className={`rounded-md border px-3 py-1.5 text-xs transition-colors ${
                scope === "field"
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-background hover:bg-muted"
              }`}
            >
              指定字段
            </button>
          </div>
        </div>

        {/* 字段选择（仅 field 模式） */}
        {scope === "field" && (
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-muted-foreground">目标字段</label>
            {availableKeys.length > 0 ? (
              <select
                className="rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                value={fieldKey}
                onChange={(e) => setFieldKey(e.target.value)}
              >
                <option value="">-- 选择字段 --</option>
                {availableKeys.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                placeholder="输入字段名，如 steps"
                className="rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                value={fieldKey}
                onChange={(e) => setFieldKey(e.target.value)}
              />
            )}
          </div>
        )}

        {/* 补充指示 */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-muted-foreground">补充指示（可选）</label>
          <textarea
            rows={2}
            placeholder="例如：重点提取每个步骤的前置条件"
            className="resize-none rounded-md border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
          />
        </div>

        {error && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <AlertCircle className="h-3.5 w-3.5" />
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" className="h-8" onClick={onCancel}>
            取消
          </Button>
          <Button size="sm" className="h-8" onClick={handleExecute}>
            执行提取
          </Button>
        </div>
      </div>
    );
  }

  // ── 提取中 ────────────────────────────────────────────────────────────────

  if (panelState === "extracting") {
    return (
      <div className="flex items-center justify-center gap-2 rounded-md border bg-muted/30 px-4 py-6 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        正在提取，请稍候...
      </div>
    );
  }

  // ── 对比结果 ──────────────────────────────────────────────────────────────

  const diff = previewData
    ? computeDiff(currentData, previewData, diffScope === "field" ? diffFieldKey : null)
    : {};

  const changedCount = Object.values(diff).filter((s) => s !== "unchanged").length;

  return (
    <div className="flex flex-col gap-3 rounded-md border bg-muted/30 p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">
          对比结果
          {changedCount > 0 ? (
            <span className="ml-2 text-xs text-muted-foreground">{changedCount} 个字段变更</span>
          ) : (
            <span className="ml-2 text-xs text-muted-foreground">无变更</span>
          )}
        </span>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2 text-xs"
          onClick={() => setPanelState("configuring")}
        >
          重新配置
        </Button>
      </div>

      {/* Diff 视图 */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        {/* 旧值 */}
        <div className="flex flex-col gap-1">
          <span className="font-medium text-muted-foreground">当前值</span>
          <div className="flex flex-col gap-1 rounded-md border bg-background p-2 font-mono">
            {Object.entries(diff).map(([k, status]) => (
              <div key={k} className={`rounded px-2 py-1 ${DIFF_COLORS[status]}`}>
                <span className="font-semibold">{k}:</span>{" "}
                {status === "removed" || status === "modified" || status === "unchanged" ? (
                  <span className="break-all text-muted-foreground">
                    {JSON.stringify(currentData[k], null, 0)?.slice(0, 120) ?? "—"}
                  </span>
                ) : (
                  <span className="italic text-muted-foreground/50">（新增）</span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 新值 */}
        <div className="flex flex-col gap-1">
          <span className="font-medium text-muted-foreground">新值</span>
          <div className="flex flex-col gap-1 rounded-md border bg-background p-2 font-mono">
            {Object.entries(diff).map(([k, status]) => (
              <div key={k} className={`rounded px-2 py-1 ${DIFF_COLORS[status]}`}>
                <span className="font-semibold">{k}:</span>{" "}
                {status !== "removed" ? (
                  <>
                    <span className="break-all text-foreground">
                      {JSON.stringify(previewData?.[k], null, 0)?.slice(0, 120) ?? "—"}
                    </span>
                    {DIFF_BADGE[status] && (
                      <span className="ml-1.5 rounded bg-yellow-200 px-1 text-yellow-800 dark:bg-yellow-800/40 dark:text-yellow-200">
                        {DIFF_BADGE[status]}
                      </span>
                    )}
                  </>
                ) : (
                  <span className="italic text-muted-foreground/50">（已删除）</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <Button size="sm" variant="ghost" className="h-8" onClick={onCancel} disabled={isSaving}>
          <X className="mr-1.5 h-3.5 w-3.5" />
          放弃
        </Button>
        <Button size="sm" className="h-8" onClick={handleApply} disabled={isSaving}>
          {isSaving ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Check className="mr-1.5 h-3.5 w-3.5" />
          )}
          应用并保存
        </Button>
      </div>
    </div>
  );
}
