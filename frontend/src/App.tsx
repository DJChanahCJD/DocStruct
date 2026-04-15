import { useEffect, useMemo, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrainCircuit, ChevronsUpDown, MessageSquare, X } from "lucide-react";
import { Toaster } from "sonner";

import { useTextModels } from "./hooks/use-api";
import { DocPreviewPanel } from "./components/doc-preview-panel";
import { DocSidebar } from "./components/doc-sidebar";
import { QaPanel } from "./components/qa-panel";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { CitationItem } from "./lib/api";

const queryClient = new QueryClient();

function AppContent() {
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [selectedDocName, setSelectedDocName] = useState("全库检索");
  const [previewMode, setPreviewMode] = useState<"preview" | "citation">("preview");
  const [previewDocId, setPreviewDocId] = useState<number | null>(null);
  const [citationSnippet, setCitationSnippet] = useState<CitationItem | null>(null);
  const [showQaPanel, setShowQaPanel] = useState(false);
  const [activeModelId, setActiveModelId] = useState("");
  const { data: textModelResponse, isLoading: isLoadingTextModels } = useTextModels();

  const textModels = textModelResponse?.models ?? [];
  const activeModel = useMemo(() => {
    return (
      textModels.find((model) => model.id === activeModelId) ??
      textModels.find((model) => model.is_default) ??
      null
    );
  }, [activeModelId, textModels]);

  useEffect(() => {
    if (!textModels.length) {
      return;
    }
    setActiveModelId((current) => {
      if (current && textModels.some((model) => model.id === current)) {
        return current;
      }
      return textModels.find((model) => model.is_default)?.id ?? textModels[0].id;
    });
  }, [textModels]);

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

  const handleOpenCitation = (citation: CitationItem) => {
    setPreviewMode("citation");
    setPreviewDocId(citation.doc_id);
    setCitationSnippet(citation);
    setShowQaPanel(true);
  };

  return (
    <div className="flex h-screen flex-col">
      <header className="flex shrink-0 items-center justify-between border-b px-4 py-2">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-blue-500" />
            <span className="font-heading text-lg font-bold">DocStruct</span>
          </div>
          <div className="hidden text-sm text-muted-foreground md:block">
            当前范围：
            <span className="ml-1 font-medium text-foreground">{selectedDocName}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger
              className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isLoadingTextModels || textModels.length === 0}
            >
              <BrainCircuit className="h-4 w-4 text-muted-foreground" />
              <div className="hidden min-w-0 text-left sm:block">
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  文本模型
                </div>
                <div className="max-w-[180px] truncate font-medium text-foreground">
                  {activeModel?.label ?? (isLoadingTextModels ? "加载中..." : "默认模型")}
                </div>
              </div>
              <ChevronsUpDown className="h-4 w-4 text-muted-foreground" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-72">
              <DropdownMenuGroup>
                <DropdownMenuLabel>全局文本模型</DropdownMenuLabel>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuRadioGroup value={activeModelId} onValueChange={setActiveModelId}>
                {textModels.map((model) => (
                  <DropdownMenuRadioItem key={model.id} value={model.id} className="items-start py-2">
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <span className="truncate font-medium text-foreground">{model.label}</span>
                      <span className="text-xs leading-5 text-muted-foreground">
                        {model.description}
                      </span>
                    </div>
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>

          <button
            onClick={() => setShowQaPanel(!showQaPanel)}
            className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm transition-colors ${
              showQaPanel
                ? "border-primary bg-primary text-primary-foreground"
                : "hover:bg-muted"
            }`}
          >
            <MessageSquare className="h-4 w-4" />
            {showQaPanel ? "关闭问答" : "开始问答"}
          </button>
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

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-[280px] shrink-0 border-r">
          <DocSidebar
            selectedId={selectedDocId}
            activeModelId={activeModelId || undefined}
            activeModelLabel={activeModel?.label}
            onSelectDoc={handleSelectDoc}
          />
        </aside>

        <main className="min-w-0 flex-1">
          {previewDocId ? (
            <DocPreviewPanel
              docId={previewDocId}
              mode={previewMode}
              citationSnippet={citationSnippet}
            />
          ) : (
            <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
              <MessageSquare className="h-16 w-16 opacity-20" />
              <p className="mt-4 text-sm">选择文档查看内容</p>
              <p className="mt-1 text-xs opacity-60">或点击“开始问答”进行提问</p>
            </div>
          )}
        </main>

        {showQaPanel && (
          <aside className="animate-in slide-in-from-right flex h-full w-[420px] shrink-0 flex-col overflow-hidden border-l bg-background duration-200">
            <header className="flex shrink-0 items-center justify-between border-b px-4 py-2">
              <h2 className="text-sm font-semibold">文档问答</h2>
              <button
                onClick={() => setShowQaPanel(false)}
                className="rounded-md p-1 transition-colors hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </header>
            <QaPanel
              selectedDocId={selectedDocId}
              activeModelId={activeModelId || undefined}
              activeModelLabel={activeModel?.label}
              onOpenCitation={handleOpenCitation}
            />
          </aside>
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
