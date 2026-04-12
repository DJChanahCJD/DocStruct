import { useState, useCallback, useRef } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FileUp, Loader2, Link } from "lucide-react";
import { useUploadDocument, useUploadUrl } from "@/hooks/use-api";
import { toast } from "sonner";

/**
 * 内联上传区域：支持文件上传和 URL 上传
 */
export function UploadZone() {
  const [dragOver, setDragOver] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
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
    } catch {
      toast.error("URL 上传失败");
    }
  }, [urlInput, uploadUrl]);

  const isPending = uploadFile.isPending || uploadUrl.isPending;

  return (
    <Tabs defaultValue="file" className="w-full">
      <TabsList className="w-full h-8">
        <TabsTrigger value="file" className="flex-1 text-xs">
          <FileUp className="h-3.5 w-3.5 mr-1" />
          文件
        </TabsTrigger>
        <TabsTrigger value="url" className="flex-1 text-xs">
          <Link className="h-3.5 w-3.5 mr-1" />
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
            const f = e.target.files?.[0];
            if (f) handleFile(f);
            e.target.value = "";
          }}
          disabled={isPending}
        />
        <div
          className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-4 transition cursor-pointer ${
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
            const f = e.dataTransfer.files[0];
            if (f) handleFile(f);
          }}
        >
          {uploadFile.isPending ? (
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          ) : (
            <FileUp className="h-6 w-6 text-muted-foreground" />
          )}
          <p className="mt-2 text-xs text-muted-foreground">
            拖拽或点击上传
          </p>
          <p className="mt-0.5 text-[10px] text-muted-foreground/60">
            PDF / DOCX / MD / TXT
          </p>
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
          <p className="text-[10px] text-muted-foreground/60">
            支持 HTML 网页、纯文本页面
          </p>
        </div>
      </TabsContent>
    </Tabs>
  );
}
