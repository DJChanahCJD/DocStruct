import { useEffect, useMemo, useState } from "react";
import { FileSearch, MapPin, Save } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import {
  EXTRACTION_SLOT_CONFIGS,
  type ExtractionEvidence,
  type ExtractionItem,
  type ExtractionSlotKey,
} from "@/lib/evidence";
import { cn } from "@/lib/utils";

interface ExtractionResultPanelProps {
  items: ExtractionItem[];
  selectedEvidence: ExtractionEvidence | null;
  onSelectEvidence: (evidence: ExtractionEvidence) => void;
  onPatchItem: (item: ExtractionItem, patch: Record<string, unknown>) => void;
}

/**
 * Display extraction objects with a review-focused detail editor.
 */
export function ExtractionResultPanel({
  items,
  selectedEvidence,
  onSelectEvidence,
  onPatchItem,
}: ExtractionResultPanelProps) {
  const groupedItems = useMemo(() => groupItemsBySlot(items), [items]);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const selectedItem = items.find((item) => item.id === selectedItemId) ?? items[0] ?? null;

  useEffect(() => {
    if (!selectedItemId && items[0]) {
      setSelectedItemId(items[0].id);
      return;
    }
    if (selectedItemId && !items.some((item) => item.id === selectedItemId)) {
      setSelectedItemId(items[0]?.id ?? null);
    }
  }, [items, selectedItemId]);

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
          {EXTRACTION_SLOT_CONFIGS.map((slotConfig) => {
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
  onClick: () => void;
}

/**
 * Render a compact object row for review navigation.
 */
function ExtractionItemRow({ item, selected, active, onClick }: ExtractionItemRowProps) {
  const primaryEvidence = getPrimaryEvidence(item);
  return (
    <button
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
  const [nameDraft, setNameDraft] = useState("");
  const [descriptionDraft, setDescriptionDraft] = useState("");
  const [detailsDraft, setDetailsDraft] = useState("");
  const [acceptanceDraft, setAcceptanceDraft] = useState("");

  useEffect(() => {
    setNameDraft(stringValue(item?.raw.name));
    setDescriptionDraft(stringValue(item?.raw.description));
    setDetailsDraft(arrayValue(item?.raw.details).join("\n"));
    setAcceptanceDraft(arrayValue(item?.raw.acceptance_criteria).join("\n"));
  }, [item]);

  if (!item) {
    return null;
  }

  const primaryEvidence = getPrimaryEvidence(item);

  const handleSave = () => {
    onPatchItem(item, {
      name: nameDraft || null,
      description: descriptionDraft || null,
      details: detailsDraft.split("\n").map((line) => line.trim()).filter(Boolean),
      acceptance_criteria: acceptanceDraft.split("\n").map((line) => line.trim()).filter(Boolean),
    });
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
          <FieldEditor label="名称" value={nameDraft} onChange={setNameDraft} rows={2} />
          <FieldEditor label="描述" value={descriptionDraft} onChange={setDescriptionDraft} rows={3} />
          {item.slot === "requirements" && (
            <>
              <FieldEditor label="功能点 / 明细" value={detailsDraft} onChange={setDetailsDraft} rows={4} />
              <FieldEditor label="验收标准" value={acceptanceDraft} onChange={setAcceptanceDraft} rows={3} />
            </>
          )}

          <div className="rounded-lg border bg-muted/15">
            <div className="border-b px-3 py-2 text-xs font-medium text-muted-foreground">证据</div>
            <div className="flex flex-col gap-2 p-3">
              {item.evidence.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无证据绑定</p>
              ) : (
                item.evidence.map((evidence, index) => (
                  <button
                    key={evidence.evidenceId ?? `${item.id}-${index}`}
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
                      <span className="font-mono text-muted-foreground">{evidence.evidenceId ?? "EVD"}</span>
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
  rows,
  onChange,
}: {
  label: string;
  value: string;
  rows: number;
  onChange: (value: string) => void;
}) {
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
 * Group extraction items by slot while preserving backend order.
 */
function groupItemsBySlot(items: ExtractionItem[]): Record<ExtractionSlotKey, ExtractionItem[]> {
  const grouped: Record<ExtractionSlotKey, ExtractionItem[]> = {
    entities: [],
    processes: [],
    requirements: [],
    interfaces: [],
    artifacts: [],
  };

  for (const item of items) {
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
 * Compare evidence entries without depending on generated object identity.
 */
function evidenceMatches(
  left: ExtractionEvidence | null,
  right: ExtractionEvidence | null,
): boolean {
  if (!left || !right) {
    return false;
  }
  if (left.evidenceId && right.evidenceId) {
    return left.evidenceId === right.evidenceId;
  }
  return left.objectId === right.objectId && left.elementId === right.elementId;
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
