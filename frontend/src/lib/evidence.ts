interface SlotConfig {
  key: string;
  label: string;
}

// Legacy five-slot config (backward compatible)
export const LEGACY_SLOT_CONFIGS: SlotConfig[] = [
  { key: "entities", label: "实体" },
  { key: "processes", label: "流程" },
  { key: "requirements", label: "需求" },
  { key: "interfaces", label: "接口" },
  { key: "artifacts", label: "产物" },
];

// Doc-type-specific slot configs
const DOC_TYPE_SLOT_CONFIGS: Record<string, SlotConfig[]> = {
  srs: [
    { key: "entities", label: "实体" },
    { key: "functional_requirements", label: "功能需求" },
    { key: "non_functional_requirements", label: "非功能需求" },
    { key: "interfaces", label: "接口" },
  ],
  api: [
    { key: "entities", label: "实体" },
    { key: "endpoints", label: "端点" },
    { key: "schemas", label: "数据模型" },
    { key: "auth", label: "认证" },
  ],
  design: [
    { key: "entities", label: "实体" },
    { key: "modules", label: "模块" },
    { key: "interfaces", label: "接口" },
    { key: "decisions", label: "架构决策" },
  ],
  test: [
    { key: "entities", label: "实体" },
    { key: "test_cases", label: "测试用例" },
    { key: "test_steps", label: "测试步骤" },
    { key: "defects", label: "缺陷" },
  ],
  manual: [
    { key: "entities", label: "实体" },
    { key: "procedures", label: "操作步骤" },
    { key: "ui_elements", label: "界面元素" },
    { key: "notes", label: "注意事项" },
  ],
  issue: [
    { key: "entities", label: "实体" },
    { key: "symptoms", label: "问题现象" },
    { key: "reproduction_steps", label: "复现步骤" },
    { key: "environment", label: "环境信息" },
  ],
};

// Active config — remains legacy for backward compat
export const EXTRACTION_SLOT_CONFIGS = LEGACY_SLOT_CONFIGS;

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
  return LEGACY_SLOT_CONFIGS;
}

/**
 * Auto-discover list-type fields from extracted data as slot configs.
 */
function discoverSlotConfigs(data: Record<string, unknown>): SlotConfig[] {
  const configs: SlotConfig[] = [];
  // Keep in sync with core/reducer.py _NON_SLOT_FIELDS.
  const knownKeys = new Set(["doc_type", "title", "version", "extra", "evidence", "base_url", "test_stage"]);
  for (const key of Object.keys(data)) {
    if (knownKeys.has(key)) continue;
    if (Array.isArray(data[key])) {
      configs.push({ key, label: key });
    }
  }
  return configs.length > 0 ? configs : LEGACY_SLOT_CONFIGS;
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

  const slotConfigs = docType
    ? getSlotConfigs(docType)
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
  if (slot === "interfaces" || slot === "endpoints") {
    const httpMethod = stringValue(item.http_method);
    const endpoint = stringValue(item.endpoint) || stringValue(item.path);
    if (httpMethod || endpoint) {
      return [httpMethod?.toUpperCase(), endpoint].filter(Boolean).join(" ");
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
    entities: "entity_type",
    processes: "process_type",
    requirements: "requirement_type",
    interfaces: "interface_type",
    artifacts: "artifact_type",
    functional_requirements: "requirement_type",
    non_functional_requirements: "requirement_type",
    endpoints: "http_method",
    auth: "auth_type",
    modules: "entity_type",
    test_cases: "test_stage",
    defects: "severity",
    procedures: "process_type",
    ui_elements: "element_type",
    symptoms: "severity",
  };
  const typeField = typeFieldBySlot[slot];
  if (typeField) {
    return stringValue(item[typeField]);
  }
  // Auto-detect: find first field ending in _type
  for (const key of Object.keys(item)) {
    if (key.endsWith("_type") && key !== "doc_type") {
      return stringValue(item[key]);
    }
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
