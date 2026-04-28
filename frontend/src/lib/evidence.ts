export const EXTRACTION_SLOT_CONFIGS = [
  { key: "entities", label: "实体" },
  { key: "processes", label: "流程" },
  { key: "requirements", label: "需求" },
  { key: "interfaces", label: "接口" },
  { key: "artifacts", label: "产物" },
] as const;

export type ExtractionSlotKey = (typeof EXTRACTION_SLOT_CONFIGS)[number]["key"];

export interface ExtractionEvidence {
  objectId: string;
  elementId: string | null;
  textSpan: string | null;
  page: number | null;
  bbox: [number, number, number, number] | null;
}

export interface ExtractionItem {
  slot: ExtractionSlotKey;
  slotLabel: string;
  id: string;
  title: string;
  typeLabel: string | null;
  description: string | null;
  evidence: ExtractionEvidence[];
  raw: Record<string, unknown>;
}

/**
 * Build display-ready extraction items and attach evidence by object_id.
 */
export function buildExtractionItems(
  extractedData: Record<string, unknown> | null | undefined,
): ExtractionItem[] {
  if (!extractedData) {
    return [];
  }

  const evidenceByObjectId = buildEvidenceMap(extractedData);
  const items: ExtractionItem[] = [];

  for (const slotConfig of EXTRACTION_SLOT_CONFIGS) {
    const rawSlotItems = extractedData[slotConfig.key];
    if (!Array.isArray(rawSlotItems)) {
      continue;
    }

    for (const rawItem of rawSlotItems) {
      if (!isRecord(rawItem)) {
        continue;
      }
      const id = stringValue(rawItem.id);
      if (!id) {
        continue;
      }

      items.push({
        slot: slotConfig.key,
        slotLabel: slotConfig.label,
        id,
        title: getItemTitle(slotConfig.key, rawItem, id),
        typeLabel: getTypeLabel(slotConfig.key, rawItem),
        description: getItemDescription(slotConfig.key, rawItem),
        evidence: evidenceByObjectId.get(id) ?? [],
        raw: rawItem,
      });
    }
  }

  return items;
}

/**
 * Return the first evidence that can drive PDF positioning.
 */
export function findFirstPositionedEvidence(items: ExtractionItem[]): ExtractionEvidence | null {
  for (const item of items) {
    const positionedEvidence = item.evidence.find((entry) => entry.page && entry.bbox);
    if (positionedEvidence) {
      return positionedEvidence;
    }
  }
  for (const item of items) {
    if (item.evidence[0]) {
      return item.evidence[0];
    }
  }
  return null;
}

/**
 * Compare evidence entries without depending on generated evidence IDs.
 */
export function evidenceMatches(
  left: ExtractionEvidence | null,
  right: ExtractionEvidence | null,
): boolean {
  if (!left || !right) {
    return false;
  }
  if (left.elementId || right.elementId) {
    return left.objectId === right.objectId && left.elementId === right.elementId;
  }
  return left.objectId === right.objectId && left.textSpan === right.textSpan && left.page === right.page;
}

/**
 * Build an object_id keyed evidence map from the extracted payload.
 */
function buildEvidenceMap(extractedData: Record<string, unknown>): Map<string, ExtractionEvidence[]> {
  const evidenceByObjectId = new Map<string, ExtractionEvidence[]>();
  const evidenceList = extractedData.evidence;
  if (!Array.isArray(evidenceList)) {
    return evidenceByObjectId;
  }

  for (const rawEvidence of evidenceList) {
    const evidence = normalizeEvidence(rawEvidence);
    if (!evidence) {
      continue;
    }
    const entries = evidenceByObjectId.get(evidence.objectId) ?? [];
    entries.push(evidence);
    evidenceByObjectId.set(evidence.objectId, entries);
  }

  return evidenceByObjectId;
}

/**
 * Normalize backend evidence JSON into a stable frontend shape.
 */
function normalizeEvidence(rawEvidence: unknown): ExtractionEvidence | null {
  if (!isRecord(rawEvidence)) {
    return null;
  }

  const objectId = stringValue(rawEvidence.object_id);
  if (!objectId) {
    return null;
  }

  return {
    objectId,
    elementId: stringValue(rawEvidence.element_id),
    textSpan: stringValue(rawEvidence.text_span),
    page: numberValue(rawEvidence.page),
    bbox: normalizeBbox(rawEvidence.bbox),
  };
}

/**
 * Normalize a bbox into [x0, y0, x1, y1] when all coordinates are finite.
 */
function normalizeBbox(value: unknown): [number, number, number, number] | null {
  if (!Array.isArray(value) || value.length !== 4) {
    return null;
  }
  const numbers = value.map((item) => Number(item));
  if (numbers.some((item) => !Number.isFinite(item))) {
    return null;
  }
  return [numbers[0], numbers[1], numbers[2], numbers[3]];
}

/**
 * Pick a compact title for a structured extraction item.
 */
function getItemTitle(
  slot: ExtractionSlotKey,
  item: Record<string, unknown>,
  fallbackId: string,
): string {
  const name = stringValue(item.name);
  if (name) {
    return name;
  }

  if (slot === "interfaces") {
    const method = stringValue(item.method);
    const path = stringValue(item.path);
    if (method || path) {
      return [method, path].filter(Boolean).join(" ");
    }
  }

  return (
    stringValue(item.title) ||
    truncateText(stringValue(item.description), 48) ||
    fallbackId
  );
}

/**
 * Pick a readable object type label from slot-specific fields.
 */
function getTypeLabel(slot: ExtractionSlotKey, item: Record<string, unknown>): string | null {
  const typeFieldBySlot: Record<ExtractionSlotKey, string> = {
    entities: "entity_type",
    processes: "process_type",
    requirements: "requirement_type",
    interfaces: "interface_type",
    artifacts: "artifact_type",
  };
  return stringValue(item[typeFieldBySlot[slot]]);
}

/**
 * Pick the best short description for a structured extraction item.
 */
function getItemDescription(slot: ExtractionSlotKey, item: Record<string, unknown>): string | null {
  if (slot === "processes") {
    return truncateText(stepsText(item.steps), 140);
  }
  if (slot === "requirements") {
    return truncateText(listText(item.points) || listText(item.criteria), 140);
  }
  if (slot === "interfaces") {
    return truncateText([item.method, item.path, item.target].map(stringValue).filter(Boolean).join(" -> "), 140);
  }
  if (slot === "artifacts") {
    return truncateText(listText(item.details), 140);
  }
  return truncateText(stringValue(item.description) || extraText(item.extra), 140);
}

/**
 * Join a scalar list into compact display text.
 */
function listText(value: unknown): string | null {
  if (!Array.isArray(value) || value.length === 0) {
    return null;
  }
  return value.map((entry) => String(entry).trim()).filter(Boolean).join("；") || null;
}

/**
 * Join process step names into compact display text.
 */
function stepsText(value: unknown): string | null {
  if (!Array.isArray(value) || value.length === 0) {
    return null;
  }
  const steps = value
    .map((entry) => (isRecord(entry) ? stringValue(entry.name) : stringValue(entry)))
    .filter(Boolean);
  return steps.join("；") || null;
}

/**
 * Build a small display string from extra object attributes.
 */
function extraText(value: unknown): string | null {
  if (!isRecord(value)) {
    return null;
  }
  return Object.entries(value)
    .slice(0, 3)
    .map(([key, entry]) => `${key}: ${String(entry).trim()}`)
    .join("；") || null;
}

/**
 * Normalize unknown values into a trimmed string or null.
 */
function stringValue(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  const text = String(value).trim();
  return text || null;
}

/**
 * Normalize unknown values into a finite number or null.
 */
function numberValue(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

/**
 * Return true when the value is a JSON-like object.
 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Truncate long text for compact object cards.
 */
function truncateText(value: string | null, limit: number): string | null {
  if (!value) {
    return null;
  }
  return value.length > limit ? `${value.slice(0, limit).trimEnd()}...` : value;
}
