interface SlotConfig {
  key: string;
  label: string;
}

const DOC_TYPE_SLOT_CONFIGS: Record<string, SlotConfig[]> = {
  srs: [
    { key: "functional_requirements", label: "功能需求" },
    { key: "non_functional_requirements", label: "非功能需求" },
  ],
  api: [
    { key: "apis", label: "接口" },
  ],
  hld: [
    { key: "modules", label: "模块" },
  ],
  tc: [
    { key: "test_cases", label: "测试用例" },
  ],
  dbdd: [
    { key: "tables", label: "数据表" },
  ],
};

export type ExtractionSlotKey = string;

export interface ExtractionEvidence {
  objectId: string;
  elementId: string | null;
  textSpan: string | null;
  page: number | null;
  bbox: [number, number, number, number] | null;
}

export interface ExtractionItem {
  id: string;
  title: string;
  slot: ExtractionSlotKey;
  slotLabel: string;
  typeLabel: string | null;
  evidence: ExtractionEvidence[];
  raw: Record<string, unknown>;
}

/**
 * Get slot configs for a given document type.
 */
export function getSlotConfigs(docType: string | null | undefined): SlotConfig[] {
  if (docType && DOC_TYPE_SLOT_CONFIGS[docType]) {
    return DOC_TYPE_SLOT_CONFIGS[docType];
  }
  return [];
}

/**
 * Auto-discover list-type fields from extracted data as slot configs.
 */
function discoverSlotConfigs(data: Record<string, unknown>): SlotConfig[] {
  const configs: SlotConfig[] = [];
  // Keep in sync with core/reducer.py _NON_SLOT_FIELDS.
  const knownKeys = new Set(["doc_type", "title", "version", "extra", "evidence", "base_url", "system_name", "target_users", "architecture_style", "technology_stack", "test_scope", "db_name", "db_type"]);
  for (const key of Object.keys(data)) {
    if (knownKeys.has(key)) continue;
    if (Array.isArray(data[key])) {
      configs.push({ key, label: key });
    }
  }
  return configs;
}

/**
 * Build display-ready extraction items and attach evidence by object_id.
 */
export function buildExtractionItems(
  extractedData: Record<string, unknown> | null | undefined,
  docType?: string | null,
): ExtractionItem[] {
  if (!extractedData) {
    return [];
  }

  const evidenceByObjectId = buildEvidenceMap(extractedData);
  const items: ExtractionItem[] = [];

  const configuredSlots = getSlotConfigs(docType);
  const slotConfigs = configuredSlots.length > 0
    ? configuredSlots
    : discoverSlotConfigs(extractedData);

  for (const slotConfig of slotConfigs) {
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

  // Interface / Endpoint: use http_method + path
  if (slot === "apis" || slot === "interfaces" || slot === "endpoints") {
    const httpMethod = stringValue(item.http_method);
    const method = stringValue(item.method) || httpMethod;
    const endpoint = stringValue(item.endpoint) || stringValue(item.path);
    if (method || endpoint) {
      return [method, endpoint].filter(Boolean).join(" ");
    }
  }

  // Auth: use auth_type
  if (slot === "auth") {
    const authType = stringValue(item.auth_type);
    if (authType) return authType;
  }

  return (
    stringValue(item.title) ||
    truncateText(stringValue(item.description), 48) ||
    truncateText(stringValue(item.summary), 48) ||
    truncateText(stringValue(item.content), 48) ||
    fallbackId
  );
}

/**
 * Pick a readable object type label from slot-specific fields.
 */
function getTypeLabel(slot: ExtractionSlotKey, item: Record<string, unknown>): string | null {
  const typeFieldBySlot: Record<string, string> = {
    functional_requirements: "priority",
    non_functional_requirements: "category",
    apis: "method",
    test_cases: "priority",
  };
  const typeField = typeFieldBySlot[slot];
  if (typeField) {
    return stringValue(item[typeField]);
  }
  return null;
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
