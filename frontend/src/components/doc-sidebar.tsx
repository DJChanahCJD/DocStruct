import { useMemo, useState } from "react";
import type { ChangeEvent } from "react";
import { Filter, Search, X } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DocCard } from "./doc-card";
import { UploadZone } from "./upload-zone";
import { useDeleteDocument, useDocuments, useRetryExtraction } from "@/hooks/use-api";
import type { DocumentRecord } from "@/lib/api";

interface DocSidebarProps {
  selectedId: number | null;
  onSelectDoc: (id: number, name: string) => void;
}

export function DocSidebar({ selectedId, onSelectDoc }: DocSidebarProps) {
  const { data: docs = [], isLoading } = useDocuments();
  const deleteDoc = useDeleteDocument();
  const retryDoc = useRetryExtraction();
  const [keyword, setKeyword] = useState("");
  const [filters, setFilters] = useState<{
    status: string[];
    docType: string[];
  }>({
    status: [],
    docType: [],
  });

  const filterOptions = useMemo(() => {
    const statusSet = new Set<string>();
    const docTypeSet = new Set<string>();
    docs.forEach((doc) => {
      if (doc.status) {
        statusSet.add(doc.status);
      }
      if (doc.doc_type) {
        docTypeSet.add(doc.doc_type);
      }
    });
    return {
      status: Array.from(statusSet),
      docType: Array.from(docTypeSet),
    };
  }, [docs]);

  const activeFilterCount = filters.status.length + filters.docType.length;

  const filtered = useMemo(() => {
    let result = docs;
    if (keyword) {
      const normalized = keyword.toLowerCase();
      const isIdSearch = /^\d+$/.test(keyword.trim());
      result = result.filter((doc: DocumentRecord) => {
        const matchFilename = doc.filename.toLowerCase().includes(normalized);
        const matchId = isIdSearch && doc.id === Number.parseInt(keyword.trim(), 10);
        return matchFilename || matchId;
      });
    }
    if (filters.status.length > 0) {
      result = result.filter((doc: DocumentRecord) => filters.status.includes(doc.status));
    }
    if (filters.docType.length > 0) {
      result = result.filter((doc: DocumentRecord) => filters.docType.includes(doc.doc_type));
    }
    return result;
  }, [docs, keyword, filters]);

  const toggleFilter = (key: "status" | "docType", value: string) => {
    setFilters((prev) => {
      const current = prev[key];
      return {
        ...prev,
        [key]: current.includes(value)
          ? current.filter((item) => item !== value)
          : [...current, value],
      };
    });
  };

  const clearFilters = () => {
    setFilters({ status: [], docType: [] });
  };

  const handleDelete = async (doc: DocumentRecord) => {
    if (!window.confirm(`确定删除 "${doc.filename}"？`)) {
      return;
    }
    try {
      await deleteDoc.mutateAsync(doc.id);
      toast.success("已删除");
    } catch {
      toast.error("删除失败");
    }
  };

  const handleRetry = async (doc: DocumentRecord) => {
    try {
      await retryDoc.mutateAsync(doc.id);
      toast.success("重试提取成功");
    } catch {
      toast.error("重试提取失败");
    }
  };

  return (
    <TooltipProvider delay={150}>
      <div className="flex h-full flex-col">
        <div className="shrink-0 border-b bg-background/90 px-4 py-4 backdrop-blur">
          <div className="mb-4">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-primary" />
              <span className="font-heading text-lg font-semibold tracking-tight">DocStruct</span>
            </div>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              结构化提取校对工作台
            </p>
          </div>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="搜索文档..."
                value={keyword}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setKeyword(event.target.value)}
                className="h-8 pr-9 pl-9 text-sm"
              />
              {keyword && (
                <button
                  onClick={() => setKeyword("")}
                  className="absolute top-1/2 right-2.5 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger className="relative h-8 rounded-md border bg-background px-2 hover:bg-accent">
                <Filter className="h-4 w-4" />
                {activeFilterCount > 0 && (
                  <Badge
                    variant="default"
                    className="absolute -top-1 -right-1 h-4 min-w-4 px-1 text-[10px]"
                  >
                    {activeFilterCount}
                  </Badge>
                )}
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                {filterOptions.status.length > 0 && (
                  <DropdownMenuGroup>
                    <DropdownMenuLabel>状态</DropdownMenuLabel>
                    {filterOptions.status.map((status) => (
                      <DropdownMenuCheckboxItem
                        key={status}
                        checked={filters.status.includes(status)}
                        onCheckedChange={() => toggleFilter("status", status)}
                      >
                        {status === "completed"
                          ? "已完成"
                          : status === "processing"
                            ? "处理中"
                            : status === "failed"
                              ? "失败"
                              : status}
                      </DropdownMenuCheckboxItem>
                    ))}
                  </DropdownMenuGroup>
                )}
                {filterOptions.status.length > 0 && filterOptions.docType.length > 0 && (
                  <DropdownMenuSeparator />
                )}
                {filterOptions.docType.length > 0 && (
                  <DropdownMenuGroup>
                    <DropdownMenuLabel>文档类型</DropdownMenuLabel>
                    {filterOptions.docType.map((docType) => (
                      <DropdownMenuCheckboxItem
                        key={docType}
                        checked={filters.docType.includes(docType)}
                        onCheckedChange={() => toggleFilter("docType", docType)}
                      >
                        {docType}
                      </DropdownMenuCheckboxItem>
                    ))}
                  </DropdownMenuGroup>
                )}
                {activeFilterCount > 0 && (
                  <>
                    <DropdownMenuSeparator />
                    <button
                      onClick={clearFilters}
                      className="w-full px-2 py-1.5 text-left text-sm text-muted-foreground hover:text-foreground"
                    >
                      清除筛选
                    </button>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        <ScrollArea className="min-h-0 flex-1 px-2 py-3">
          {isLoading ? (
            <div className="py-8 text-center text-sm text-muted-foreground">加载中...</div>
          ) : filtered.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">暂无文档</div>
          ) : (
            <div className="w-full space-y-2">
              {filtered.map((doc: DocumentRecord) => (
                <DocCard
                  key={doc.id}
                  doc={doc}
                  selected={selectedId === doc.id}
                  onSelect={() => onSelectDoc(doc.id, doc.filename)}
                  onDelete={() => handleDelete(doc)}
                  onRetry={() => handleRetry(doc)}
                />
              ))}
            </div>
          )}
        </ScrollArea>
        <Separator />
        <div className="shrink-0 bg-background/90 p-3 backdrop-blur">
          <UploadZone />
        </div>
      </div>
    </TooltipProvider>
  );
}
