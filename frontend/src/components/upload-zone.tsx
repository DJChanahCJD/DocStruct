import { useCallback, useRef, useState } from "react";
import { FileUp, Link, Loader2, File } from "lucide-react";
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
export function UploadZone({ activeModelId, activeModelLabel }: UploadZoneProps) {
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
    set