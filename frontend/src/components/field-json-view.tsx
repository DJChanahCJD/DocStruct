import { FieldInlineEditor } from "@/components/field-inline-editor";

interface FieldJsonViewProps {
  data: Record<string, unknown>;
  docId: number;
  /** 单字段确认新值后的回调，父组件负责合并和持久化 */
  onFieldApply: (fieldKey: string, newValue: unknown) => Promise<void>;
}

/**
 * 将 extracted_data 按顶层 key 拆分展示，
 * 每行渲染一个 FieldInlineEditor 支持行级追问修改。
 */
export function FieldJsonView({ data, docId, onFieldApply }: FieldJsonViewProps) {
  const entries = Object.entries(data);

  return (
    <div className="font-mono text-sm leading-relaxed space-y-0.5">
      <div className="text-muted-foreground">{`{`}</div>
      <div className="pl-4 space-y-0.5">
        {entries.map(([key, value]) => (
          <FieldInlineEditor
            key={key}
            fieldKey={key}
            fieldValue={value}
            docId={docId}
            onApply={onFieldApply}
          />
        ))}
      </div>
      <div className="text-muted-foreground">{`}`}</div>
    </div>
  );
}
