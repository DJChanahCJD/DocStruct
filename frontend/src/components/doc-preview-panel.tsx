import { useState, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Loader2, Pencil, X, Check } from "lucide-react";
import { useDocument, useUpdateDocument } from "@/hooks/use-api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import type { CitationItem } from "@/lib/api";

// 类型断言绕过 react-markdown v10 类型定义问题
const Markdown = ReactMarkdown as React.FC<{
  remarkPlugins?: unknown[];
  children?: string;
}>;

interface DocPreviewPanelProps {
  docId: number | null;
  mode: "preview" | "citation";
  citationSnippet?: CitationItem | null;
}

/**
 * 文档预览面板（内联右侧列）。
 * 显示选中文档的原文、JSON（支持编辑）和错误信息。
 */
export function DocPreviewPanel({
  docId,
  mode,
  citationSnippet,
}: DocPreviewPanelProps) {
  const { data: doc, isLoading } = useDocument(docId);
  const updateDoc = useUpdateDocument(docId ?? 0);

  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);

  // 切换文档时退出编辑模式
  useEffect(() => {
    setIsEditing(false);
    setJsonError(null);
  }, [docId]);

  if (!docId) return null;

  /** 进入编辑模式，填充当前 JSON */
  const handleEdit = () => {
    setEditText(
      doc?.extracted_data
        ? JSON.stringify(doc.extracted_data, null, 2)
        : "{}",
    );
    setJsonError(null);
    setIsEditing(true);
  };

  /** 校验 JSON 并在输入时给出即时反馈 */
  const handleTextChange = (value: string) => {
    setEditText(value);
    try {
      JSON.parse(value);
      setJsonError(null);
    } catch (e) {
      setJsonError((e as Error).message);
    }
  };

  /** 保存 — 再次校验后提交 */
  const handleSave = async () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(editText);
    } catch (e) {
      setJsonError((e as Error).message);
      return;
    }
    try {
      await updateDoc.mutateAsync({ extracted_data: parsed });
      toast.success("保存成功");
      setIsEditing(false);
    } catch {
      toast.error("保存失败");
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setJsonError(null);
  };

  return (
    <div className="w-full flex-1 flex flex-col h-full overflow-hidden bg-background">
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="mt-2 text-sm">加载中...</span>
        </div>
      ) : doc ? (
        <Tabs defaultValue="json" className="flex flex-col flex-1 overflow-hidden">
          {/* Tab 切换栏 */}
          <div className="px-4 py-2 border-b shrink-0">
            <TabsList className="w-full">
              <TabsTrigger value="json" className="flex-1">
                JSON
              </TabsTrigger>
              <TabsTrigger value="raw" className="flex-1">
                原文
              </TabsTrigger>
              {doc.error_message && (
                <TabsTrigger value="error" className="flex-1">
                  错误
                </TabsTrigger>
              )}
            </TabsList>
          </div>

          {/* 引用片段 - 固定 */}
          {mode === "citation" && citationSnippet && (
            <div className="px-4 py-3 border-b shrink-0">
              <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
                <div className="mb-1 text-xs font-medium uppercase text-primary">
                  引用片段
                </div>
                {citationSnippet.title_path && (
                  <p className="mb-2 text-xs text-muted-foreground">
                    {citationSnippet.title_path}
                  </p>
                )}
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {citationSnippet.snippet}
                </p>
              </div>
            </div>
          )}

          {/* 内容区 - 可滚动 */}
          <ScrollArea className="flex-1 h-0 min-h-0 px-4 py-3">
            <TabsContent value="raw" className="mt-0">
              <div className="prose prose-sm dark:prose-invert max-w-none text-sm leading-relaxed">
                <Markdown remarkPlugins={[remarkGfm]}>
                  {doc.parsed_content || "暂无原文内容"}
                </Markdown>
              </div>
            </TabsContent>

            <TabsContent value="json" className="mt-0">
              {isEditing ? (
                <div className="flex flex-col gap-2">
                  {/* 编辑工具栏 */}
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">
                      编辑 extracted_data
                    </span>
                    <div className="flex gap-1.5">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs"
                        onClick={handleCancel}
                        disabled={updateDoc.isPending}
                      >
                        <X className="mr-1 h-3 w-3" />
                        取消
                      </Button>
                      <Button
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={handleSave}
                        disabled={!!jsonError || updateDoc.isPending}
                      >
                        {updateDoc.isPending ? (
                          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                        ) : (
                          <Check className="mr-1 h-3 w-3" />
                        )}
                        保存
                      </Button>
                    </div>
                  </div>
                  {/* JSON 文本编辑区 */}
                  <textarea
                    className="min-h-[320px] w-full resize-y rounded-lg border bg-muted p-3 font-mono text-xs leading-relaxed outline-none focus:ring-1 focus:ring-primary"
                    value={editText}
                    onChange={(e) => handleTextChange(e.target.value)}
                    spellCheck={false}
                  />
                  {jsonError && (
                    <p className="text-xs text-destructive">{jsonError}</p>
                  )}
                </div>
              ) : (
                <div className="relative group">
                  {/* 只读 JSON 与编辑按钮 */}
                  <Button
                    size="sm"
                    variant="outline"
                    className="absolute right-2 top-2 h-7 px-2 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={handleEdit}
                  >
                    <Pencil className="mr-1 h-3 w-3" />
                    编辑
                  </Button>
                  <pre className="whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs">
                    {doc.extracted_data
                      ? JSON.stringify(doc.extracted_data, null, 2)
                      : "暂无结构化数据"}
                  </pre>
                </div>
              )}
            </TabsContent>

            {doc.error_message && (
              <TabsContent value="error" className="mt-0">
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {doc.error_message}
                </div>
              </TabsContent>
            )}
          </ScrollArea>
        </Tabs>
      ) : (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <p className="text-sm">文档不存在</p>
        </div>
      )}
    </div>
  );
}
