import { useCallback, useRef, useState } from "react";
import { FileUp, Link, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useUploadDocument, useUploadUrl } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const DOC_TYPE_OPTIONS = [
  { value: "srs", label: "SRS 需求文档" },
  { value: "api", label: "API 文档" },
  { value: "design", label: "设计文档" },
  { value: "test", label: "测试文档" },
  { value: "manual", label: "用户手册" },
  { value: "issue", label: "问题单" },
  { value: "unknown", label: "未知类型" },
] as const;

interface UploadZoneProps {
  activeModelId?: string | null;
  activeModelLabel?: string;
}

/**
 * 内联上传区域：支持文件上传和 URL 上传，并复用全局文本模型。
 */
export function UploadZone({ activeModelId, activeModelLabel }: UploadZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [docType, setDocType] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadFile = useUploadDocument();
  const uploadUrl = useUploadUrl();

  const handleFile = useCallback(
    async (file: File) => {
      if (!docType) {
        toast.error("请先选择文档类型");
        return;
      }
      const allowed = [".pdf", ".docx", ".md", ".txt"];
      const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      if (!allowed.includes(ext)) {
        toast.error(`不支持的文件类型: ${ext}`);
        return;
      }
      try {
        const res = await uploadFile.mutateAsync({
          file,
          doc_type: docType,
          llm_model: activeModelId ?? undefined,
        });
        toast.success(res.message);
      } catch {
        toast.error("上传失败");
      }
    },
    [activeModelId, docType, uploadFile],
  );

  const handleUrlSubmit = useCallback(async () => {
    const url = urlInput.trim();
    if (!url) {
      toast.error("请输入 URL");
      return;
    }
    if (!docType) {
      toast.error("请先选择文档类型");
      return;
    }
    try {
      const res = await uploadUrl.mutateAsync({
        url,
        doc_type: docType,
        llm_model: activeModelId ?? undefined,
      });
      toast.success(res.message);
      setUrlInput("");
    } catch {
      toast.error("URL 上传失败");
    }
  }, [activeModelId, docType, urlInput, uploadUrl]);

  const isPending = uploadFile.isPending || uploadUrl.isPending;

  return (
    <div className="space-y-2">
      <div className="rounded-md border bg-muted/40 px-3 py-2">
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
          当前文本模型
        </p>
        <p className="mt-1 truncate text-xs font-medium text-foreground">
          {activeModelLabel ?? "默认模型"}
        </p>
      </div>

      <Tabs defaultValue="file" className="w-full">
        <div className="mb-2 space-y-1">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">文档类型</p>
          <select
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            disabled={isPending}
            className="flex h-8 w-full rounded-md border border-input bg-background px-2 text-xs text-foreground outline-none ring-offset-background"
          >
            <option value="">请选择上传类型</option>
            {DOC_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <p className="text-[10px] text-muted-foreground/60">上传时显式指定类型，系统将直接按该类型抽取</p>
        </div>
        <TabsList className="h-8 w-full">
          <TabsTrigger value="file" className="flex-1 text-xs">
            <FileUp className="mr-1 h-3.5 w-3.5" />
            文件
          </TabsTrigger>
          <TabsTrigger value="url" className="flex-1 text-xs">
            <Link className="mr-1 h-3.5 w-3.5" />
            URL
          </TabsTrigger>
        </TabsList>

        <TabsContent value="file" className="mt-2">
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.docx,.md,.txt"
            onChange={(e) => {
              const selectedFile = e.target.files?.[0];
              if (selectedFile) handleFile(selectedFile);
              e.target.value = "";
            }}
            disabled={isPending}
          />
          <div
            className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-4 transition ${
              dragOver
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-muted-foreground/50"
            }`}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const droppedFile = e.dataTransfer.files[0];
              if (droppedFile) handleFile(droppedFile);
            }}
          >
            {uploadFile.isPending ? (
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : (
              <FileUp className="h-6 w-6 text-muted-foreground" />
            )}
            <p className="mt-2 text-xs text-muted-foreground">拖拽或点击上传</p>
            <p className="mt-0.5 text-[10px] text-muted-foreground/60">PDF / DOCX / MD / TXT</p>
          </div>
        </TabsContent>

        <TabsContent value="url" className="mt-2">
          <div className="space-y-2">
            <div className="flex gap-1.5">
              <Input
                type="url"
                placeholder="https://..."
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleUrlSubmit();
                }}
                disabled={uploadUrl.isPending}
                className="h-8 text-xs"
              />
              <Button
                size="sm"
                onClick={handleUrlSubmit}
                disabled={isPending || !urlInput.trim() || !docType}
                className="h-8 px-3"
              >
                {uploadUrl.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  "提交"
                )}
              </Button>
            </div>
            <p className="text-[10px] text-muted-foreground/60">支持 HTML 网页、纯文本页面</p>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

