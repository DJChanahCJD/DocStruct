import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { DocSidebar } from "./components/doc-sidebar";
import { QaPanel } from "./components/qa-panel";
import { DocPreviewPanel } from "./components/doc-preview-panel";

const queryClient = new QueryClient();

function AppContent() {
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [selectedDocName, setSelectedDocName] = useState("全库检索");
  const [previewMode, setPreviewMode] = useState<"preview" | "citation">("preview");
  const [previewDocId, setPreviewDocId] = useState<number | null>(null);
  const [citationSnippet, setCitationSnippet] = useState<string | null>(null);

  const handleSelectDoc = (id: number, name: string) => {
    setSelectedDocId(id);
    setSelectedDocName(name);
    setPreviewMode("preview");
    setPreviewDocId(id);
  };

  const handleClearSelection = () => {
    setSelectedDocId(null);
    setSelectedDocName("全库检索");
    setPreviewDocId(null);
  };

  const handleOpenCitation = (docId: number, snippet: string) => {
    setPreviewMode("citation");
    setPreviewDocId(docId);
    setCitationSnippet(snippet);
  };

  return (
    <div className="flex h-screen flex-col">
      {/* 顶栏 */}
      <header className="border-b px-4 py-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-blue-500" />
            <span className="font-heading text-lg font-bold">DocStruct</span>
          </div>
          <div className="text-sm text-muted-foreground">
            当前:{" "}
            <span className="font-medium text-foreground">
              {selectedDocName}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {selectedDocId && (
            <button
              onClick={handleClearSelection}
              className="rounded-md border px-2 py-1 text-sm hover:bg-muted"
            >
              全库模式
            </button>
          )}
        </div>
      </header>

      {/* 主体：两列或三列 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 左侧文档列表 */}
        <aside className="w-[280px] shrink-0 border-r">
          <DocSidebar
            selectedId={selectedDocId}
            onSelectDoc={handleSelectDoc}
          />
        </aside>

        {/* 中央问答区 */}
        <main className="flex-1 min-w-0">
          <QaPanel
            selectedDocId={selectedDocId}
            selectedDocName={selectedDocName}
            onOpenCitation={handleOpenCitation}
          />
        </main>

        {/* 右侧预览面板（有选中文档时显示） */}
        {selectedDocId && (
          <DocPreviewPanel
            docId={previewDocId ?? selectedDocId}
            mode={previewMode}
            citationSnippet={citationSnippet}
          />
        )}
      </div>

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
