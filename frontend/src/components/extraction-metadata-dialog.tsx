import { useEffect, useMemo, useState } from "react";
import { Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import {
  getMetadataFieldConfigs,
  buildDrafts,
  buildPatch,
} from "@/lib/metadata";

interface ExtractionMetadataDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  docType: string | null | undefined;
  extractedData: Record<string, unknown> | null | undefined;
  isSaving?: boolean;
  onSave: (patch: Record<string, unknown>) => void;
}

/**
 * Edit document-level fields stored at the top level of extracted_data.
 */
export function ExtractionMetadataDialog({
  open,
  onOpenChange,
  docType,
  extractedData,
  isSaving = false,
  onSave,
}: ExtractionMetadataDialogProps) {
  const fieldConfigs = useMemo(
    () => getMetadataFieldConfigs(docType, extractedData),
    [docType, extractedData],
  );
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!open || !extractedData) {
      return;
    }
    setDrafts(buildDrafts(extractedData, fieldConfigs));
  }, [extractedData, fieldConfigs, open]);

  const handleSave = () => {
    onSave(buildPatch(fieldConfigs, drafts));
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>文档元数据</DialogTitle>
          <DialogDescription>
            编辑结构化 JSON 顶层字段，不影响对象证据绑定。
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3 py-2 sm:grid-cols-2">
          {fieldConfigs.map((fieldConfig) => (
            <MetadataFieldEditor
              key={fieldConfig.key}
              label={fieldConfig.label}
              value={drafts[fieldConfig.key] ?? ""}
              rows={fieldConfig.rows}
              onChange={(value) => setDrafts((current) => ({ ...current, [fieldConfig.key]: value }))}
            />
          ))}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={isSaving || fieldConfigs.length === 0}>
            <Save data-icon="inline-start" />
            保存元数据
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Render a compact metadata textarea field.
 */
function MetadataFieldEditor({
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
