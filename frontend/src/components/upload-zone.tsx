import { useCallback, useRef, useState } from "react";
import { FileUp, Link, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useUploadDocument, useUploadUrl } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DocTypeSelectorDialog } from "@/components/doc-type-selector-dialog";

interface UploadZoneProps {
  activeModelId?: string | null;
  activeModelLabel?: string;
}

/**
 * 内联上传区域：支持文件上传和 URL 上传，上传后弹出类型选择对话框。
 */
export function UploadZone({ activeModelId }: UploadZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingUrl, setPendingUrl] = useState<string>("");
  const [showTypeDialog, setShowTypeDialog] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadFile = useUploadDocument();
  const uploadUrl = useUploadUrl();

  const isPending = uploadFile.isPending || uploadUrl.isPending;

  // Handle file selection (stores file and opens type dialog)
  const handleFileSelected = useCallback((file: File) => {
    const allowed = [".pdf", ".docx", ".md", ".txt"];
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!allowed.includes(ext)) {
      toast.error(`不支持的文件类型: ${ext}`);
      return;
    }
    setPendingFile(file);
    setPendingUrl("");
    setShowTypeDialog(true);
  }, []);

  // Handle URL submit (stores URL and opens type dialog)
  const handleUrlSubmit = useCallback(() => {
    const url = urlInput.trim();
    if (!url) {
      toast.error("请输入 URL");
      return;
    }
    setPendingUrl(url);
    setPendingFile(null);
    setShowTypeDialog(true);
  }, [urlInput]);

  // Handle type selection confirmation
  const handleTypeConfirm = useCallback(async (docType: string) => {
    setShowTypeDialog(false);

    if (pendingFile) {
      // File upload
      try {
        const res = await uploadFile.mutateAsync({
          file: pendingFile,
          doc_type: docType,
          llm_model: activeModelId ?? undefined,
        });
        toast.success(res.message);
      } catch {
        toast.error("上传失败");
      } finally {
        setPendingFile(null);
      }
    } else if (pendingUrl) {
      // URL upload
      try {
        const res = await uploadUrl.mutateAsync({
          url: pendingUrl,
          doc_type: docType,
          llm_model: activeModelId ?? undefined,
        });
        toast.success(res.message);
        setUrlInput("");
      } catch {
        toast.error("URL 上传失败");
      } finally {
        setPendingUrl("");
      }
    }
  }, [pendingFile, pendingUrl, activeModelId, uploadFile, uploadUrl]);

  // Handle dialog cancellation
  const handleDialogClose = useCallback((open: boolean) => {
    setShowTypeDialog(open);
    if (!open) {
      // Clear pending states when dialog is cancelled
      setPendingFile(null);
      setPendingUrl("");
    }
  }, []);

  return (
    <div className="space-y-2">
      <Tabs defaultValue="file" className="w-full">
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
              if (selectedFile) handleFileSelected(selectedFile);
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
              if (droppedFile) handleFileSelected(droppedFile);
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
                disabled={isPending || !urlInput.trim()}
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

      {/* Document Type Selector Dialog */}
      <DocTypeSelectorDialog
        open={showTypeDialog}
        onOpenChange={handleDialogClose}
        onConfirm={handleTypeConfirm}
        fileName={pendingFile?.name}
      />
    </div>
  );
}
