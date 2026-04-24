import { useCallback, useRef, useState } from "react";
import { FileUp, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { DocTypeSelectorDialog } from "@/components/doc-type-selector-dialog";
import { useUploadDocument } from "@/hooks/use-api";

export function UploadZone() {
  const [dragOver, setDragOver] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [showTypeDialog, setShowTypeDialog] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadFile = useUploadDocument();

  const handleFileSelected = useCallback((file: File) => {
    const allowed = [".pdf", ".docx", ".md", ".txt"];
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!allowed.includes(ext)) {
      toast.error(`不支持的文件类型: ${ext}`);
      return;
    }
    setPendingFile(file);
    setShowTypeDialog(true);
  }, []);

  const handleTypeConfirm = useCallback(async (docType: string) => {
    setShowTypeDialog(false);
    if (!pendingFile) {
      return;
    }

    try {
      const response = await uploadFile.mutateAsync({
        file: pendingFile,
        doc_type: docType,
      });
      toast.success(response.message);
    } catch {
      toast.error("上传失败");
    } finally {
      setPendingFile(null);
    }
  }, [pendingFile, uploadFile]);

  const handleDialogClose = useCallback((open: boolean) => {
    setShowTypeDialog(open);
    if (!open) {
      setPendingFile(null);
    }
  }, []);

  return (
    <div className="space-y-2">
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        accept=".pdf,.docx,.md,.txt"
        onChange={(event) => {
          const selectedFile = event.target.files?.[0];
          if (selectedFile) {
            handleFileSelected(selectedFile);
          }
          event.target.value = "";
        }}
        disabled={uploadFile.isPending}
      />
      <div
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-4 transition ${
          dragOver
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-muted-foreground/50"
        }`}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          const droppedFile = event.dataTransfer.files[0];
          if (droppedFile) {
            handleFileSelected(droppedFile);
          }
        }}
      >
        {uploadFile.isPending ? (
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        ) : (
          <FileUp className="h-6 w-6 text-muted-foreground" />
        )}
        <p className="mt-2 text-xs text-muted-foreground">
          {uploadFile.isPending ? "上传文件中..." : "拖拽或点击上传"}
        </p>
        <p className="mt-0.5 text-[10px] text-muted-foreground/60">
          {uploadFile.isPending ? "上传后将自动开始解析与提取" : "PDF / DOCX / MD / TXT"}
        </p>
      </div>

      <DocTypeSelectorDialog
        open={showTypeDialog}
        onOpenChange={handleDialogClose}
        onConfirm={handleTypeConfirm}
        fileName={pendingFile?.name}
      />
    </div>
  );
}
