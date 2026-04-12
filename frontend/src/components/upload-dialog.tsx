import { useState, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Upload, FileUp, Loader2, Link } from "lucide-react";
import { useUploadDocument, useUploadUrl } from "@/hooks/use-api";
import { toast } from "sonner";

/**
 * 上传对话框：支持文件上传和 URL 上传两种方式
 */
export function UploadDialog() {
  const [open, setOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const uploadFile = useUploadDocument();
  const uploadUrl = useUploadUrl();

  const handleFile = useCallback(
    async (file: File) => {
      const allowed = [".pdf", ".docx", ".md", ".txt"];
      const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      if (!allowed.includes(ext)) {
        toast.error(`不支持的文件类型: ${ext}`);
        return;
      }
      try {
        const res = await uploadFile.mutateAsync(file);
        toast.success(res.message);
        setOpen(false);
      } catch {
        toast.error("上传失败");
      }
    },
    [uploadFile],
  );

  const handleUrlSubmit = useCallback(async () => {
    const url = urlInput.trim();
    if (!url) {
      toast.error("请输入 URL");
      return;
    }
    try {
      const res = await uploadUrl.mutateAsync(url);
      toast.success(res.message);
      setUrlInput("");
      setOpen(false);
    } catch {
      toast.error("URL 上传失败");
    }
  }, [urlInput, uploadUrl]);

  const isPending = uploadFile.isPending || uploadUrl.isPending;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90">
          <Upload className="h-4 w-4" />
          上传
        </button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>上传文档</DialogTitle>
        </DialogHeader>
        <Tabs defaultValue="file" className="mt-2">
          <TabsList className="w-full">
            <TabsTrigger value="file" className="flex-1">
              <FileUp className="h-4 w-4 mr-1.5" />
              文件上传
            </TabsTrigger>
            <TabsTrigger value="url" className="flex-1">
              <Link className="h-4 w-4 mr-1.5" />
              URL 上传
            </TabsTrigger>
          </TabsList>

          {/* 文件上传 Tab */}
          <TabsContent value="file" className="mt-2">
            <div
              className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition ${
                dragOver
                  ? "border-primary bg-primary/5"
                  : "border-muted-foreground/25"
              }`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                const f = e.dataTransfer.files[0];
                if (f) handleFile(f);
              }}
            >
              {uploadFile.isPending ? (
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              ) : (
                <FileUp className="h-8 w-8 text-muted-foreground" />
              )}
              <p className="mt-3 text-sm text-muted-foreground">
                拖拽文件至此，或点击选择
              </p>
              <p className="mt-1 text-xs text-muted-foreground/60">
                支持 PDF、DOCX、MD、TXT
              </p>
              <label className="mt-4">
                <input
                  type="file"
                  className="hidden"
                  accept=".pdf,.docx,.md,.txt"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleFile(f);
                  }}
                  disabled={isPending}
                />
                <span className="cursor-pointer rounded-md border px-4 py-2 text-sm hover:bg-muted">
                  选择文件
                </span>
              </label>
            </div>
          </TabsContent>

          {/* URL 上传 Tab */}
          <TabsContent value="url" className="mt-2">
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                输入公开网页 URL，系统将抓取内容并自动分类处理。
              </p>
              <div className="flex gap-2">
                <Input
                  type="url"
                  placeholder="https://example.com/document"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleUrlSubmit();
                  }}
                  disabled={uploadUrl.isPending}
                />
                <Button
                  onClick={handleUrlSubmit}
                  disabled={isPending || !urlInput.trim()}
                >
                  {uploadUrl.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    "提交"
                  )}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground/60">
                支持 HTML 网页、纯文本页面
              </p>
            </div>
          </TabsContent>
        </Tabs>
        <DialogClose className="sr-only">关闭</DialogClose>
      </DialogContent>
    </Dialog>
  );
}
