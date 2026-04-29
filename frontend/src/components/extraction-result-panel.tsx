import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FileSearch, MapPin, Save } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import {
  evidenceMatches,
  type ExtractionEvidence,
  type ExtractionItem,
  type ExtractionSlotKey,
} from "@/lib/evidence";
import { cn } from "@/lib/utils";

type DetailFieldKind = "text" | "list" | "steps" | "select";

interface DetailFieldConfig {
  key: string;
  label: string;
  kind: DetailFieldKind;
  rows: number;
  options?: DetailFieldOption[];
}

interface DetailFieldOption {
  value: string;
  label: string;
}

const TYPE_FIELD_OPTIONS: Record<string, DetailFieldOption[]> = {
  entity_type: [
    { value: "actor", label: "actor - 人或角色" },
    { value: "system", label: "system - 系统或模块" },
    { value: "data", label: "data - 数据对象" },
    { value: "other", label: "other - 其他实体" },
  ],
  process_type: [
    { value: "business", label: "business - 业务流程" },
    { value: "technical", label: "technical - 技术流程" },
    { value: "test", label: "test - 测试流程" },
    { value: "other", label: "other - 其他流程" },
  ],
  requirement_type: [
    { value: "functional", label: "functional - 功能需求" },
    { value: "non_functional", label: "non_functional - 非功能需求" },
    { value: "other", label: "other - 其他需求" },
  ],
  interface_type: [
    { value: "http", label: "http - HTTP API" },
    { value: "rpc", label: "rpc - RPC 调用" },
    { value: "message", label: "message - 消息通道" },
    { value: "ui", label: "ui - 用户界面入口" },
    { value: "database", label: "database - 数据库交换" },
    { value: "file", label: "file - 文件交换" },
    { value: "other", label: "other - 其他接口" },
  ],
  artifact_type: [
    { value: "test_case", label: "test_case - 测试用例" },
    { value: "decision", label: "decision - 决策记录" },
    { value: "table", label: "table - 表格产物" },
    { value: "issue", label: "issue - 问题记录" },
    { value: "section", label: "section - 文档章节" },
    { value: "other", label: "other - 其他产物" },
  ],
  http_method: [
    { value: "", label: "未指定" },
    { value: "get", label: "GET - 读取资源" },
    { value: "post", label: "POST - 创建或提交" },
    { value: "put", label: "PUT - 整体更新" },
    { value: "patch", label: "PATCH - 局部更新" },
    { value: "delete", label: "DELETE - 删除资源" },
    { value: "head", label: "HEAD - 读取响应头" },
    { value: "options", label: "OPTIONS - 查询支持方法" },
  ],
};

const DETAIL_FIELD_CONFIGS: Record<string, DetailFieldConfig[]> = {
  entities: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "entity_type", label: "实体类型", kind: "select", rows: 1, options: TYPE_FIELD_OPTIONS.entity_type },
  ],
  processes: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "process_type", label: "流程类型", kind: "select", rows: 1, options: TYPE_FIELD_OPTIONS.process_type },
    { key: "steps", label: "步骤", kind: "steps", rows: 5 },
  ],
  requirements: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "requirement_type", label: "需求类型", kind: "select", rows: 1, options: TYPE_FIELD_OPTIONS.requirement_type },
    { key: "points", label: "功能点 / 明细", kind: "list", rows: 4 },
    { key: "criteria", label: "验收标准", kind: "list", rows: 3 },
  ],
  functional_requirements: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "points", label: "功能点", kind: "list", rows: 4 },
    { key: "criteria", label: "验收标准", kind: "list", rows: 3 },
  ],
  non_functional_requirements: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "category", label: "分类", kind: "text", rows: 1 },
    { key: "description", label: "描述", kind: "text", rows: 3 },
  ],
  interfaces: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "interface_type", label: "接口类型", kind: "select", rows: 1, options: TYPE_FIELD_OPTIONS.interface_type },
    { key: "http_method", label: "HTTP 方法", kind: "select", rows: 1, options: TYPE_FIELD_OPTIONS.http_method },
    { key: "endpoint", label: "入口标识", kind: "text", rows: 2 },
    { key: "provider", label: "提供方", kind: "text", rows: 1 },
    { key: "consumer", label: "调用方", kind: "text", rows: 1 },
  ],
  endpoints: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "http_method", label: "HTTP 方法", kind: "select", rows: 1, options: TYPE_FIELD_OPTIONS.http_method },
    { key: "path", label: "路径", kind: "text", rows: 1 },
    { key: "summary", label: "功能简述", kind: "text", rows: 2 },
    { key: "request_schema", label: "请求结构", kind: "text", rows: 2 },
    { key: "response_schema", label: "响应结构", kind: "text", rows: 2 },
  ],
  schemas: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "description", label: "用途说明", kind: "text", rows: 2 },
    { key: "fields", label: "字段", kind: "list", rows: 5 },
  ],
  auth: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "auth_type", label: "认证类型", kind: "text", rows: 1 },
    { key: "description", label: "说明", kind: "text", rows: 3 },
  ],
  modules: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "responsibility", label: "职责", kind: "text", rows: 2 },
    { key: "sub_modules", label: "子模块", kind: "list", rows: 3 },
  ],
  decisions: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "rationale", label: "理由", kind: "text", rows: 3 },
    { key: "alternatives", label: "替代方案", kind: "list", rows: 3 },
  ],
  test_cases: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "precondition", label: "前置条件", kind: "text", rows: 2 },
    { key: "expected_result", label: "预期结果", kind: "text", rows: 2 },
  ],
  test_steps: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "action", label: "操作", kind: "text", rows: 2 },
    { key: "expected", label: "预期行为", kind: "text", rows: 2 },
  ],
  defects: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "severity", label: "严重程度", kind: "text", rows: 1 },
    { key: "description", label: "描述", kind: "text", rows: 3 },
  ],
  procedures: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "steps", label: "步骤", kind: "steps", rows: 5 },
  ],
  ui_elements: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "element_type", label: "元素类型", kind: "text", rows: 1 },
    { key: "location", label: "所在位置", kind: "text", rows: 1 },
  ],
  notes: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "content", label: "内容", kind: "text", rows: 4 },
  ],
  symptoms: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "description", label: "现象描述", kind: "text", rows: 3 },
  ],
  reproduction_steps: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "action", label: "操作", kind: "text", rows: 2 },
    { key: "expected", label: "预期", kind: "text", rows: 2 },
    { key: "actual", label: "实际", kind: "text", rows: 2 },
  ],
  environment: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "value", label: "值", kind: "text", rows: 1 },
  ],
  artifacts: [
    { key: "name", label: "名称", kind: "text", rows: 2 },
    { key: "artifact_type", label: "产物类型", kind: "select", rows: 1, options: TYPE_FIELD_OPTIONS.artifact_type },
    { key: "details", label: "要点", kind: "list", rows: 5 },
  ],
};

/**
 * Generate default field configs for an unknown slot by inspecting item data.
 */
function getFieldConfigs(slot: string, sampleItem: Record<string, unknown> | null): DetailFieldConfig[] {
  const known = DETAIL_FIELD_CONFIGS[slot];
  if (known) return known;

  // Auto-generate from item keys (skip id, evidence_element_ids)
  if (sampleItem) {
    const configs: DetailFieldConfig[] = [];
    for (const key of Object.keys(sampleItem)) {
      if (key === "id" || key === "evidence_element_ids") continue;
      const value = sampleItem[key];
      if (Array.isArray(value)) {
        if (value.length > 0 && typeof value[0] === "object" && value[0] !== null && "name" in value[0]) {
          configs.push({ key, label: key, kind: "steps", rows: 4 });
        } else {
          configs.push({ key, label: key, kind: "list", rows: 4 });
        }
      } else {
        configs.push({ key, label: key, kind: "text", rows: 2 });
      }
    }
    if (configs.length > 0) return configs;
  }

  // Minimal fallback
  return [
    { key: "name", label: "名称", kind: "text", rows: 2 },
  ];
}

interface ExtractionResultPanelProps {
  items: ExtractionItem[];
  selectedEvidence: ExtractionEvidence | null;
  onSelectEvidence: (evidence: ExtractionEvidence) => void;
  onPatchItem: (item: ExtractionItem, patch: Record<string, unknown>) => void;
  onSelectedItemChange?: (item: ExtractionItem | null) => void;
}

/**
 * Display extraction objects with a review-focused detail editor.
 */
export function ExtractionResultPanel({
  items,
  selectedEvidence,
  onSelectEvidence,
  onPatchItem,
  onSelectedItemChange,
}: ExtractionResultPanelProps) {
  const groupedItems = useMemo(() => groupItemsBySlot(items), [items]);
  const slotConfigs = useMemo(() => deriveSlotConfigs(items), [items]);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const itemRowRefs = useRef(new Map<string, HTMLButtonElement>());
  const selectedItemFromEvidence = selectedEvidence
    ? items.find((item) => item.evidence.some((entry) => evidenceMatches(entry, selectedEvidence)))
    : null;
  const selectedItem = selectedItemFromEvidence ?? items.find((item) => item.id === selectedItemId) ?? items[0] ?? null;

  const registerItemRowRef = useCallback((itemId: string, node: HTMLButtonElement | null) => {
    if (node) {
      itemRowRefs.current.set(itemId, node);
      return;
    }
    itemRowRefs.current.delete(itemId);
  }, []);

  useEffect(() => {
    if (!selectedItemId && items[0]) {
      setSelectedItemId(items[0].id);
      return;
    }
    if (selectedItemId && !items.some((item) => item.id === selectedItemId)) {
      setSelectedItemId(items[0]?.id ?? null);
    }
  }, [items, selectedItemId]);

  useEffect(() => {
    if (!selectedEvidence || !selectedItem) {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      itemRowRefs.current.get(selectedItem.id)?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [selectedEvidence, selectedItem]);

  useEffect(() => {
    onSelectedItemChange?.(selectedItem);
  }, [onSelectedItemChange, selectedItem]);

  if (items.length === 0) {
    return (
      <div className="flex h-full min-h-0 flex-col items-center justify-center gap-3 px-8 text-center text-sm text-muted-foreground">
        <FileSearch className="opacity-40" />
        <div>
          <p className="font-medium text-foreground">暂无结构化结果</p>
          <p className="mt-1">提取完成后，这里会按对象展示可定位证据。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid h-full min-h-0 grid-cols-[minmax(160px,0.72fr)_minmax(220px,1fr)]">
      <ScrollArea className="min-h-0 border-r">
        <div className="flex flex-col gap-4 p-3">
          {slotConfigs.map((slotConfig) => {
            const slotItems = groupedItems[slotConfig.key];
            if (slotItems.length === 0) {
              return null;
            }

            return (
              <section key={slotConfig.key} className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <h4 className="text-sm font-semibold text-foreground">{slotConfig.label}</h4>
                  <Badge variant="secondary">{slotItems.length}</Badge>
                </div>
                <div className="flex flex-col gap-1.5">
                  {slotItems.map((item) => (
                    <ExtractionItemRow
                      key={`${item.slot}-${item.id}`}
                      item={item}
                      selected={item.id === selectedItem?.id}
                      active={item.evidence.some((entry) => evidenceMatches(entry, selectedEvidence))}
                      refCallback={registerItemRowRef}
                      onClick={() => {
                        setSelectedItemId(item.id);
                        const evidence = getPrimaryEvidence(item);
                        if (evidence) {
                          onSelectEvidence(evidence);
                        }
                      }}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      </ScrollArea>

      <ExtractionDetail
        item={selectedItem}
        selectedEvidence={selectedEvidence}
        onSelectEvidence={onSelectEvidence}
        onPatchItem={onPatchItem}
      />
    </div>
  );
}

interface ExtractionItemRowProps {
  item: ExtractionItem;
  selected: boolean;
  active: boolean;
  refCallback: (itemId: string, node: HTMLButtonElement | null) => void;
  onClick: () => void;
}

/**
 * Render a compact object row for review navigation.
 */
function ExtractionItemRow({ item, selected, active, refCallback, onClick }: ExtractionItemRowProps) {
  const primaryEvidence = getPrimaryEvidence(item);
  return (
    <button
      ref={(node) => refCallback(item.id, node)}
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full flex-col gap-1 rounded-md border px-2.5 py-2 text-left transition-colors",
        selected ? "border-primary bg-primary/5" : "border-border hover:bg-muted/45",
        active && "ring-1 ring-primary/20",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[11px] text-muted-foreground">{item.id}</span>
        {primaryEvidence?.page && (
          <span className="text-[11px] font-medium text-primary">P{primaryEvidence.page}</span>
        )}
      </div>
      <div className="line-clamp-2 text-sm font-medium text-foreground">{item.title}</div>
      <div className="flex items-center gap-1.5">
        {item.typeLabel && (
          <Badge variant="outline" className="h-4 px-1.5 text-[10px]">
            {item.typeLabel}
          </Badge>
        )}
        {item.evidence.length > 1 && (
          <span className="text-[11px] text-muted-foreground">{item.evidence.length} 条证据</span>
        )}
      </div>
    </button>
  );
}

interface ExtractionDetailProps {
  item: ExtractionItem | null;
  selectedEvidence: ExtractionEvidence | null;
  onSelectEvidence: (evidence: ExtractionEvidence) => void;
  onPatchItem: (item: ExtractionItem, patch: Record<string, unknown>) => void;
}

/**
 * Render object details, evidence shortcuts, and patch controls.
 */
function ExtractionDetail({
  item,
  selectedEvidence,
  onSelectEvidence,
  onPatchItem,
}: ExtractionDetailProps) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const selectedEvidenceRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!item) {
      setDrafts({});
      return;
    }
    setDrafts(buildDrafts(item));
  }, [item]);

  useEffect(() => {
    if (!selectedEvidence) {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      selectedEvidenceRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [item, selectedEvidence]);

  if (!item) {
    return null;
  }

  const primaryEvidence = getPrimaryEvidence(item);
  const fieldConfigs = getFieldConfigs(item.slot, item.raw);

  const handleSave = () => {
    onPatchItem(item, buildPatch(fieldConfigs, drafts));
  };

  return (
    <div className="flex min-h-0 flex-col">
      <div className="shrink-0 border-b px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{item.id}</span>
              <Badge variant="secondary">{item.slotLabel}</Badge>
              {item.typeLabel && <Badge variant="outline">{item.typeLabel}</Badge>}
            </div>
            <h4 className="mt-2 line-clamp-2 text-base font-semibold text-foreground">{item.title}</h4>
          </div>
          {primaryEvidence && (
            <Button variant="secondary" size="sm" onClick={() => onSelectEvidence(primaryEvidence)}>
              <MapPin data-icon="inline-start" />
              定位
            </Button>
          )}
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-4 p-4">
          {fieldConfigs.map((fieldConfig) => (
            <FieldEditor
              key={fieldConfig.key}
              label={fieldConfig.label}
              value={drafts[fieldConfig.key] ?? ""}
              onChange={(value) => setDrafts((current) => ({ ...current, [fieldConfig.key]: value }))}
              options={fieldConfig.options}
              rows={fieldConfig.rows}
            />
          ))}

          <div className="rounded-lg border bg-muted/15">
            <div className="border-b px-3 py-2 text-xs font-medium text-muted-foreground">证据</div>
            <div className="flex flex-col gap-2 p-3">
              {item.evidence.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无证据绑定</p>
              ) : (
                item.evidence.map((evidence, index) => (
                  <button
                    key={`${evidence.objectId}-${evidence.elementId ?? evidence.textSpan ?? index}`}
                    ref={(node) => {
                      if (evidenceMatches(evidence, selectedEvidence)) {
                        selectedEvidenceRef.current = node;
                      }
                    }}
                    type="button"
                    onClick={() => onSelectEvidence(evidence)}
                    className={cn(
                      "rounded-md border px-3 py-2 text-left text-xs transition-colors",
                      evidenceMatches(evidence, selectedEvidence)
                        ? "border-primary bg-primary/5"
                        : "border-border bg-background hover:bg-muted/45",
                    )}
                  >
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="font-mono text-muted-foreground">{evidence.elementId ?? "无元素"}</span>
                      {evidence.page && <span className="font-medium text-primary">P{evidence.page}</span>}
                    </div>
                    <div className="line-clamp-3 leading-5 text-foreground">
                      {evidence.textSpan ?? "无文本片段"}
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          <Button onClick={handleSave}>
            <Save data-icon="inline-start" />
            保存当前对象
          </Button>
        </div>
      </ScrollArea>
    </div>
  );
}

/**
 * Render a labeled textarea editor.
 */
function FieldEditor({
  label,
  value,
  options,
  rows,
  onChange,
}: {
  label: string;
  value: string;
  options?: DetailFieldOption[];
  rows: number;
  onChange: (value: string) => void;
}) {
  if (options) {
    return (
      <label className="flex flex-col gap-1.5">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        <select
          value={normalizeSelectValue(value, options)}
          onChange={(event) => onChange(event.target.value)}
          className="h-8 w-full rounded-lg border border-input bg-background px-2.5 py-1 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    );
  }

  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <Textarea
        value={value}
        rows={rows}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-0 resize-none bg-muted/10 text-sm leading-6"
      />
    </label>
  );
}

/**
 * Derive slot configs from extraction items in appearance order.
 */
function deriveSlotConfigs(items: ExtractionItem[]): { key: string; label: string }[] {
  const seen = new Set<string>();
  const configs: { key: string; label: string }[] = [];
  for (const item of items) {
    if (!seen.has(item.slot)) {
      seen.add(item.slot);
      configs.push({ key: item.slot, label: item.slotLabel });
    }
  }
  return configs;
}

/**
 * Group extraction items by slot while preserving backend order.
 */
function groupItemsBySlot(items: ExtractionItem[]): Record<string, ExtractionItem[]> {
  const grouped: Record<string, ExtractionItem[]> = {};

  for (const item of items) {
    if (!grouped[item.slot]) {
      grouped[item.slot] = [];
    }
    grouped[item.slot].push(item);
  }

  return grouped;
}

/**
 * Choose the strongest evidence entry for item-level positioning.
 */
function getPrimaryEvidence(item: ExtractionItem): ExtractionEvidence | null {
  return item.evidence.find((entry) => entry.page && entry.bbox) ?? item.evidence[0] ?? null;
}

/**
 * Build editable text drafts from the selected object.
 */
function buildDrafts(item: ExtractionItem): Record<string, string> {
  const drafts: Record<string, string> = {};
  for (const fieldConfig of getFieldConfigs(item.slot, item.raw)) {
    drafts[fieldConfig.key] = draftValue(item.raw[fieldConfig.key], fieldConfig.kind);
    if (fieldConfig.options && !fieldConfig.options.some((option) => option.value === drafts[fieldConfig.key])) {
      drafts[fieldConfig.key] = defaultSelectValue(fieldConfig.options);
    }
  }
  return drafts;
}

/**
 * Convert textarea drafts back into the structured patch payload.
 */
function buildPatch(fieldConfigs: DetailFieldConfig[], drafts: Record<string, string>): Record<string, unknown> {
  const patch: Record<string, unknown> = {};
  for (const fieldConfig of fieldConfigs) {
    patch[fieldConfig.key] = patchValue(drafts[fieldConfig.key] ?? "", fieldConfig.kind);
  }
  return patch;
}

/**
 * Normalize a raw field value into editable textarea text.
 */
function draftValue(value: unknown, kind: DetailFieldKind): string {
  if (kind === "list") {
    return arrayValue(value).join("\n");
  }
  if (kind === "steps") {
    return stepValue(value).join("\n");
  }
  return stringValue(value);
}

/**
 * Normalize textarea text into the field shape expected by extracted objects.
 */
function patchValue(value: string, kind: DetailFieldKind): unknown {
  const text = value.trim();
  if (kind === "list") {
    return linesValue(value);
  }
  if (kind === "steps") {
    return linesValue(value).map((line) => ({ name: line }));
  }
  if (kind === "select") {
    return text || null;
  }
  return text || null;
}

/**
 * Normalize a select draft to a valid option value.
 */
function normalizeSelectValue(value: string, options: DetailFieldOption[]): string {
  if (options.some((option) => option.value === value)) {
    return value;
  }
  return defaultSelectValue(options);
}

/**
 * Return the safe fallback value for a select field.
 */
function defaultSelectValue(options: DetailFieldOption[]): string {
  if (options.some((option) => option.value === "other")) {
    return "other";
  }
  return options[0]?.value ?? "";
}

/**
 * Normalize process steps into editable step names.
 */
function stepValue(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => {
      if (isRecord(item)) {
        return stringValue(item.name);
      }
      return stringValue(item);
    })
    .filter(Boolean);
}

/**
 * Normalize an unknown value into a string.
 */
function stringValue(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

/**
 * Normalize an unknown value into a string list.
 */
function arrayValue(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item));
}

/**
 * Split textarea content into non-empty trimmed lines.
 */
function linesValue(value: string): string[] {
  return value.split("\n").map((line) => line.trim()).filter(Boolean);
}

/**
 * Return true when the value is a JSON-like object.
 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
