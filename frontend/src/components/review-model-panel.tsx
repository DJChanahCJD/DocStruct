import { useEffect, useMemo, useState } from "react";
import { Loader2, Sparkles, Save, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useReviewModel, useReviewNodeReExtract, useUpdateReviewModel } from "@/hooks/use-api";
import type { DocumentReviewModel, ReviewField, ReviewNode } from "@/lib/api";

interface ReviewModelPanelProps {
  docId: number;
}

interface ReviewNodeListItem {
  nodeId: string;
  title: string;
  subtitle?: string | null;
  kind: "meta" | "item";
}

function serializeValue(value: unknown) {
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value, null, 2);
}

function parseValue(text: string, valueType: string, originalValue: unknown): unknown {
  if (valueType === "string") {
    return text;
  }
  try {
    return JSON.parse(text);
  } catch {
    return originalValue;
  }
}

function createNodeIndex(reviewModel: DocumentReviewModel) {
  const index = new Map<string, ReviewNode>();

  for (const field of reviewModel.meta_fields) {
    index.set(field.node_id, {
      node_id: field.node_id,
      node_type: "meta",
      label: "文档元信息",
      group_key: null,
      title: field.label,
      fields: [field],
    });
  }

  for (const group of reviewModel.groups) {
    for (const item of group.items) {
      index.set(item.node_id, {
        node_id: item.node_id,
        node_type: "item",
        label: group.label,
        group_key: group.group_key,
        title: item.title,
        fields: item.fields,
      });
    }
  }

  return index;
}

function collectNodeList(reviewModel: DocumentReviewModel): ReviewNodeListItem[] {
  const nodes: ReviewNodeListItem[] = reviewModel.meta_fields.map((field) => ({
    nodeId: field.node_id,
    title: field.label,
    subtitle: null,
    kind: "meta",
  }));

  for (const group of reviewModel.groups) {
    for (const item of group.items) {
      nodes.push({
        nodeId: item.node_id,
        title: item.title,
        subtitle: item.summary ?? group.label,
        kind: "item",
      });
    }
  }

  return nodes;
}

function fieldsChanged(fields: ReviewField[], draftValues: Record<string, string>) {
  return fields.some((field) => {
    const nextValue = parseValue(draftValues[field.field_key] ?? "", field.value_type, field.value);
    return JSON.stringify(nextValue) !== JSON.stringify(field.value);
  });
}

export function ReviewModelPanel({ docId }: ReviewModelPanelProps) {
  const { data: reviewModel, isLoading } = useReviewModel(docId);
  const updateReview = useUpdateReviewModel(docId);
  const reExtractNode = useReviewNodeReExtract(docId);

  const nodeIndex = useMemo(() => (reviewModel ? createNodeIndex(reviewModel) : new Map()), [reviewModel]);
  const nodeList = useMemo(() => (reviewModel ? collectNodeList(reviewModel) : []), [reviewModel]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const [instruction, setInstruction] = useState("");
  const [previewNode, setPreviewNode] = useState<ReviewNode | null>(null);

  const selectedNode = selectedNodeId ? nodeIndex.get(selectedNodeId) ?? null : null;

  useEffect(() => {
    if (!selectedNodeId && nodeList.length > 0) {
      setSelectedNodeId(nodeList[0].nodeId);
    }
  }, [nodeList, selectedNodeId]);

  useEffect(() => {
    if (!selectedNode) {
      setDraftValues({});
      setPreviewNode(null);
      setInstruction("");
      return;
    }
    setDraftValues(
      Object.fromEntries(
        selectedNode.fields.map((field: ReviewField) => [field.field_key, serializeValue(field.value)]),
      ),
    );
    setPreviewNode(null);
    setInstruction("");
  }, [selectedNode]);

  const hasChanges = selectedNode ? fieldsChanged(selectedNode.fields, draftValues) : false;

  const handleSave = async () => {
    if (!selectedNode) {
      return;
    }
    const changes = selectedNode.fields
      .map((field: ReviewField) => {
        const value = parseValue(draftValues[field.field_key] ?? "", field.value_type, field.value);
        return {
          node_id: selectedNode.node_id,
          field_key: field.field_key,
          value,
          changed: JSON.stringify(value) !== JSON.stringify(field.value),
        };
      })
      .filter((item: { changed: boolean }) => item.changed)
      .map(({ changed: _changed, ...change }: { changed: boolean; node_id: string; field_key: string; value: unknown }) => change);

    if (changes.length === 0) {
      toast.info("当前节点没有变化");
      return;
    }

    try {
      const result = await updateReview.mutateAsync({ changes, reindex: true });
      if (result.warning) {
        toast.warning(result.warning);
      } else {
        toast.success("修改已保存，并已同步重建索引");
      }
    } catch {
      toast.error("保存失败");
    }
  };

  const handlePreviewReExtract = async () => {
    if (!selectedNode) {
      return;
    }
    try {
      const result = await reExtractNode.mutateAsync({
        node_id: selectedNode.node_id,
        instruction: instruction.trim() || undefined,
        use_rag: true,
      });
      setPreviewNode(result.node);
    } catch {
      toast.error("预览重提取失败");
    }
  };

  const applyPreviewToDraft = () => {
    if (!previewNode) {
      return;
    }
    setDraftValues(
      Object.fromEntries(previewNode.fields.map((field) => [field.field_key, serializeValue(field.value)])),
    );
    toast.success("预览结果已应用到草稿");
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在加载审核视图...
      </div>
    );
  }

  if (!reviewModel || nodeList.length === 0) {
    return <div className="py-12 text-center text-sm text-muted-foreground">暂无可审核的结构化节点</div>;
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
      <div className="rounded-md border bg-muted/20 p-2">
        <p className="mb-2 px-2 text-[11px] uppercase tracking-wide text-muted-foreground">审核节点</p>
        <div className="space-y-1">
          {nodeList.map((node) => (
            <button
              key={node.nodeId}
              type="button"
              onClick={() => setSelectedNodeId(node.nodeId)}
              className={`w-full rounded-md px-3 py-2 text-left transition ${
                selectedNodeId === node.nodeId
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-muted"
              }`}
            >
              <div className="truncate text-sm font-medium">{node.title}</div>
              <div
                className={`mt-0.5 truncate text-[11px] ${
                  selectedNodeId === node.nodeId ? "text-primary-foreground/80" : "text-muted-foreground"
                }`}
              >
                {node.kind === "meta" ? "元字段" : node.subtitle || "Item"}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-4 rounded-md border bg-muted/10 p-4">
        {selectedNode && (
          <>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{selectedNode.label}</p>
                <h3 className="mt-1 text-lg font-semibold">{selectedNode.title}</h3>
              </div>
              <Button onClick={handleSave} disabled={!hasChanges || updateReview.isPending}>
                {updateReview.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                保存节点修改
              </Button>
            </div>

            <div className="space-y-3">
              {selectedNode.fields.map((field: ReviewField) => (
                <label key={field.field_key} className="block space-y-1.5">
                  <span className="text-sm font-medium text-foreground">{field.label}</span>
                  <Textarea
                    value={draftValues[field.field_key] ?? ""}
                    onChange={(event) =>
                      setDraftValues((prev) => ({ ...prev, [field.field_key]: event.target.value }))
                    }
                    rows={field.value_type === "string" ? 3 : 6}
                    spellCheck={false}
                    className="bg-background font-mono text-sm"
                  />
                </label>
              ))}
            </div>

            <div className="rounded-md border bg-background p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">AI 预览重提取</p>
                  <p className="text-xs text-muted-foreground">只针对当前节点生成预览，不会直接写库。</p>
                </div>
                <Button
                  variant="secondary"
                  onClick={handlePreviewReExtract}
                  disabled={reExtractNode.isPending}
                >
                  {reExtractNode.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="mr-2 h-4 w-4" />
                  )}
                  生成预览
                </Button>
              </div>
              <Textarea
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                placeholder="补充修改意图，例如：统一术语，补全缺失前置条件"
                rows={2}
                className="mt-3 bg-background text-sm"
              />
            </div>

            {previewNode && (
              <div className="rounded-md border border-dashed bg-background p-3">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">AI 预览结果</p>
                    <p className="text-xs text-muted-foreground">确认后可一键覆盖当前草稿。</p>
                  </div>
                  <Button variant="secondary" onClick={applyPreviewToDraft}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    应用到草稿
                  </Button>
                </div>
                <div className="grid gap-3 lg:grid-cols-2">
                  <NodeFieldPreview title="当前草稿" fields={selectedNode.fields} draftValues={draftValues} />
                  <NodeFieldPreview
                    title="AI 预览"
                    fields={previewNode.fields}
                    draftValues={Object.fromEntries(
                      previewNode.fields.map((field: ReviewField) => [field.field_key, serializeValue(field.value)]),
                    )}
                  />
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function NodeFieldPreview({
  title,
  fields,
  draftValues,
}: {
  title: string;
  fields: ReviewField[];
  draftValues: Record<string, string>;
}) {
  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <p className="mb-2 text-xs font-medium text-muted-foreground">{title}</p>
      <div className="space-y-2">
        {fields.map((field) => (
          <div key={field.field_key} className="rounded bg-background p-2">
            <div className="text-xs font-medium text-muted-foreground">{field.label}</div>
            <pre className="mt-1 overflow-x-auto whitespace-pre-wrap font-mono text-xs leading-relaxed">
              {draftValues[field.field_key] ?? ""}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}
