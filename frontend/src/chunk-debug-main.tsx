import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Toaster } from "sonner";

import { ChunkDebugPanel } from "@/components/chunk-debug-panel";
import { Button } from "@/components/ui/button";
import "./index.css";

const queryClient = new QueryClient();

/**
 * Standalone entry point for the chunk debug page.
 * Activated by opening /chunk-debug.html?docId=<id>.
 */
function ChunkDebugApp() {
  const params = new URLSearchParams(window.location.search);
  const docId = Number(params.get("docId")) || null;

  return (
    <div className="flex h-screen flex-col bg-background">
      <div className="flex shrink-0 items-center gap-3 border-b px-5 py-3">
        <a href="/">
          <Button variant="ghost" size="sm">
            <ArrowLeft data-icon="inline-start" />
            返回主应用
          </Button>
        </a>
        <p className="text-sm font-medium text-foreground">
          分块调试{docId ? ` · Doc #${docId}` : ""}
        </p>
      </div>
      <div className="min-h-0 flex-1">
        <ChunkDebugPanel docId={docId} />
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ChunkDebugApp />
      <Toaster position="top-center" />
    </QueryClientProvider>
  </StrictMode>,
);
