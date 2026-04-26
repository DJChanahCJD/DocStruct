import { useMemo } from "react";
import { FileSearch, MapPin } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
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
}

/**
 * Display extraction objects as clickable evidence anchors.
 */
export function ExtractionResultPanel({
  items,
  selectedEvidence,
  onSelectEvidence,
}: ExtractionResultPanelProps) {
  const groupedItems = useMemo(() => groupItemsBySlot(items), [items]);

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
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-4 px-4 py-4">
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
              <div className="flex flex-col gap-2">
                {slotItems.map((item) => (
                  <ExtractionItemButton
                    key={`${item.slot}-${item.id}`}
                    item={item}
                    selectedEvidence={selectedEvidence}
                    onSelectEvidence={onSelectEvidence}
                  />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </ScrollArea>
  );
}

interface ExtractionItemButtonProps {
  item: ExtractionItem;
  selectedEvidence: ExtractionEvidence | null;
  onSelectEvidence: (evidence: ExtractionEvidence) => void;
}

/**
 * Render one structured object with its evidence shortcuts.
 */
function ExtractionItemButton({
  item,
  selectedEvidence,
  onSelectEvidence,
}: ExtractionItemButtonProps) {
  const primaryEvidence = getPrimaryEvidence(item);
  const active = item.evidence.some((entry) => evidenceMatches(entry, selectedEvidence));

  return (
    <div
      role={primaryEvidence ? "button" : undefined}
      tabIndex={primaryEvidence ? 0 : -1}
      aria-disabled={!primaryEvidence}
      onClick={() => {
        if (primaryEvidence) {
          onSelectEvidence(primaryEvidence);
        }
      }}
      onKeyDown={(event) => {
        if (!primaryEvidence) {
          return;
        }
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelectEvidence(primaryEvidence);
        }
      }}
      className={cn(
        "flex w-full flex-col gap-2 rounded-lg border bg-background px-3 py-3 text-left transition-colors",
        active ? "border-primary bg-primary/5 ring-1 ring-primary/20" : "border-border hover:bg-muted/45",
        !primaryEvidence && "cursor-default opacity-70 hover:bg-background",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-muted-foreground">{item.id}</span>
            {item.typeLabel && (
              <Badge variant="outline" className="h-4 px-1.5 text-[10px]">
                {item.typeLabel}
              </Badge>
            )}
          </div>
          <div className="mt-1 line-clamp-2 text-sm font-medium text-foreground">{item.title}</div>
          {item.description && (
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
              {item.description}
            </p>
          )}
        </div>
        <EvidenceStatus evidence={primaryEvidence} />
      </div>

      {item.evidence.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {item.evidence.map((entry, index) => (
            <EvidenceChip
              key={entry.evidenceId ?? `${item.id}-${index}`}
              evidence={entry}
              active={evidenceMatches(entry, selectedEvidence)}
              onSelectEvidence={onSelectEvidence}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Render the compact evidence location status.
 */
function EvidenceStatus({ evidence }: { evidence: ExtractionEvidence | null }) {
  if (!evidence) {
    return <span className="shrink-0 text-xs text-muted-foreground">无证据</span>;
  }

  if (evidence.page && evidence.bbox) {
    return (
      <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
        <MapPin />
        P{evidence.page}
      </span>
    );
  }

  return <span className="shrink-0 text-xs text-muted-foreground">文本证据</span>;
}

interface EvidenceChipProps {
  evidence: ExtractionEvidence;
  active: boolean;
  onSelectEvidence: (evidence: ExtractionEvidence) => void;
}

/**
 * Render a secondary evidence shortcut for multi-evidence objects.
 */
function EvidenceChip({ evidence, active, onSelectEvidence }: EvidenceChipProps) {
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onSelectEvidence(evidence);
      }}
      className={cn(
        "inline-flex h-6 items-center rounded-md border px-2 text-[11px] font-medium",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-muted/35 text-muted-foreground",
      )}
    >
      {evidence.evidenceId ?? "EVD"}
      {evidence.page ? ` · P${evidence.page}` : ""}
    </button>
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
