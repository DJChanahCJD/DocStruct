import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { Toaster } from "sonner";

import { DocPreviewPanel } from "./components/doc-preview-panel";
import { DocSidebar } from "./components/doc-sidebar";

const queryClient = new QueryClient();

function AppContent() {
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [hasUnsavedRawChanges, setHasUnsavedRawChanges] = useState(false);

  const confirmDiscardRawChanges = () => {
    if (!hasUnsavedRawChanges) {
      return true;
    }
    return window.confirm("当前 Markdown 校对内容尚未保存，确定要离开吗？");
  };

  const handleSelectDoc = (id: number) => {
    if (!confirmDiscardRawChanges()) {
      return;
    }
    setSelectedDocId(id);
    setHasUnsavedRawChanges(false);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <aside className="h-screen w-[280px] shrink-0 border-r bg-muted/20">
        <DocSidebar selectedId={selectedDocId} onSelectDoc={handleSelectDoc} />
      </aside>

      <main className="min-w-0 flex-1">
        {selectedDocId ? (
          <DocPreviewPanel
            docId={selectedDocId}
            onRawDirtyChange={setHasUnsavedRawChanges}
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-4 px-8 text-center text-muted-foreground">
            <div className="rounded-3xl border border-dashed border-border/70 bg-muted/20 p-6">
              <FileText className="h-14 w-14 opacity-30" />
            </div>
            <div className="space-y-2">
              <p className="text-base font-medium text-foreground">选择左侧文档开始校对</p>
              <p className="text-sm">上传后可直接在右侧对照原文修订 Markdown 和结构化 JSON。</p>
            </div>
          </div>
        )}
      </main>

      <Toaster position="top-center" />
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}
