/**
 * Shared metadata field configs and utilities for document extraction metadata.
 */

export type MetadataFieldKind = "text" | "list";

export interface MetadataFieldConfig {
  key: string;
  label: string;
  kind: MetadataFieldKind;
  rows: number;
}

export const METADATA_FIELD_CONFIGS: Record<string, MetadataFieldConfig[]> = {
  default: [
    { key: "title", label: "文档标题", kind: "text", rows: 1 },
    { key: "version", label: "版本", kind: "text", rows: 1 },
  ],
  api: [
    { key: "title", label: "文档标题", kind: "text", rows: 1 },
    { key: "version", label: "版本", kind: "text", rows: 1 },
    { key: "base_url", label: "Base URL", kind: "text", rows: 1 },
  ],
  srs: [
    { key: "title", label: "文档标题", kind: "text", rows: 1 },
    { key: "version", label: "版本", kind: "text", rows: 1 },
    { key: "system_name", label: "系统名称", kind: "text", rows: 1 },
    { key: "target_users", label: "目标用户", kind: "list", rows: 3 },
  ],
  hld: [
    { key: "title", label: "文档标题", kind: "text", rows: 1 },
    { key: "version", label: "版本", kind: "text", rows: 1 },
    { key: "architecture_style", label: "架构风格", kind: "text", rows: 1 },
    { key: "technology_stack", label: "技术栈", kind: "list", rows: 3 },
  ],
  tc: [
    { key: "title", label: "文档标题", kind: "text", rows: 1 },
    { key: "version", label: "版本", kind: "text", rows: 1 },
    { key: "test_scope", label: "测试范围", kind: "text", rows: 2 },
  ],
  dbdd: [
    { key: "title", label: "文档标题", kind: "text", rows: 1 },
    { key: "version", label: "版本", kind: "text", rows: 1 },
    { key: "db_name", label: "数据库名称", kind: "text", rows: 1 },
    { key: "db_type", label: "数据库类型", kind: "text", rows: 1 },
  ],
};

/**
 * Select editable metadata fields for the current document type.
 */
export function getMetadataFieldConfigs(
  docType: string | null | undefined,
  extractedData: Record<string, unknown> | null | undefined,
): MetadataFieldConfig[] {
  if (!extractedData) {
    return [];
  }
  const configured = METADATA_FIELD_CONFIGS[docType ?? ""] ?? METADATA_FIELD_CONFIGS.default;
  return configured.filter((fieldConfig) => {
    if (fieldConfig.key in extractedData) {
      return true;
    }
    return fieldConfig.key === "title" || fieldConfig.key === "version";
  });
}

/**
 * Build editable metadata drafts from extracted_data.
 */
export function buildDrafts(
  extractedData: Record<string, unknown>,
  fieldConfigs: MetadataFieldConfig[],
): Record<string, string> {
  const drafts: Record<string, string> = {};
  for (const fieldConfig of fieldConfigs) {
    drafts[fieldConfig.key] = draftValue(extractedData[fieldConfig.key], fieldConfig.kind);
  }
  return drafts;
}

/**
 * Convert metadata drafts back into a top-level extracted_data patch.
 */
export function buildPatch(
  fieldConfigs: MetadataFieldConfig[],
  drafts: Record<string, string>,
): Record<string, unknown> {
  const patch: Record<string, unknown> = {};
  for (const fieldConfig of fieldConfigs) {
    patch[fieldConfig.key] = patchValue(drafts[fieldConfig.key] ?? "", fieldConfig.kind);
  }
  return patch;
}

/**
 * Normalize a raw metadata value into editable text.
 */
function draftValue(value: unknown, kind: MetadataFieldKind): string {
  if (kind === "list") {
    return Array.isArray(value) ? value.map((item) => String(item)).join("\n") : "";
  }
  return value === null || value === undefined ? "" : String(value);
}

/**
 * Normalize edited metadata text into the expected JSON value.
 */
function patchValue(value: string, kind: MetadataFieldKind): unknown {
  if (kind === "list") {
    return value.split("\n").map((line) => line.trim()).filter(Boolean);
  }
  const text = value.trim();
  return text || null;
}

/**
 * Build a human-readable metadata summary string for tooltip display.
 */
export function formatMetadataSummary(
  docType: string | null | undefined,
  extractedData: Record<string, unknown> | null | undefined,
): string {
  if (!extractedData) return "无元数据";
  const configs = getMetadataFieldConfigs(docType, extractedData);
  const parts: string[] = [];
  for (const config of configs) {
    const value = extractedData[config.key];
    if (value === null || value === undefined || value === "") continue;
    const display = Array.isArray(value) ? value.join(", ") : String(value);
    parts.push(`${config.label}: ${display}`);
  }
  return parts.join("\n") || "无元数据";
}
