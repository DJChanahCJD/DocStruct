import { useState, useMemo } from "react";
import type { ChangeEvent } from "react";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { DocCard } from "./doc-card";
import { UploadZone } from "./upload-zone";
import { Search, X, Filter } from "lucide-react";
import { useDocuments, useDeleteDocument, useReindex } from "@/hooks/use-api";
import { toast } from "sonner";
import type { DocumentRecord } from "@/lib/api";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";

interface DocSidebarProps {
  selectedId: number | null;
  onSelectDoc: (id: number, name: string) => void;
}

export function DocSidebar({ selectedId, onSelectDoc }: DocSidebarProps) {
  const { data: docs = [], isLoading } = useDocuments();
  const deleteDoc = useDeleteDocument();
  const reindex = useReindex();
  const [keyword, setKeyword] = useState("");
  const [filters, setFilters] = useState<{
    status: string[];
    docType: string[];
    sourceType: string[];
  }>({
    status: [],
    docType: [],
    sourceType: [],
  });

  // 动态获取可用的筛选选项
  const filterOptions = useMemo(() => {
    const statusSet = new Set<string>();
    const docTypeSet = new Set<string>();
    const sourceTypeSet = new Set<string>();
    docs.forEach((d) => {
      if (d.status) statusSet.add(d.status);
      if (d.doc_type) docTypeSet.add(d.doc_type);
      if (d.source_type) sourceTypeSet.add(d.source_type);
    });
    return {
      status: Array.from(statusSet),
      docType: Array.from(docTypeSet),
      sourceType: Array.from(sourceTypeSet),
    };
  }, [docs]);

  const activeFilterCount =
    filters.status.length + filters.docType.length + filters.sourceType.length;

  const filtered = useMemo(() => {
    let result = docs;
    if (keyword) {
      const kw = keyword.toLowerCase();
      const isIdSearch = /^\d+$/.test(keyword.trim());
      result = result.filter((d: DocumentRecord) => {
        const matchFilename = d.filename.toLowerCase().includes(kw);
        const matchId = isIdSearch && d.id === parseInt(keyword.trim(), 10);
        return matchFilename || matchId;
      });
    }
    if (filters.status.length > 0) {
      result = result.filter((d: DocumentRecord) =>
        filters.status.includes(d.status),
      );
    }
    if (filters.docType.length > 0) {
      result = result.filter((d: DocumentRecord) =>
        filters.docType.includes(d.doc_type),
      );
    }
    if (filters.sourceType.length > 0) {
      result = result.filter((d: DocumentRecord) =>
        filters.sourceType.includes(d.source_type),
      );
    }
    return result;
  }, [docs, keyword, filters]);

  const toggleFilter = (
    key: "status" | "docType" | "sourceType",
    value: string,
  ) => {
    setFilters((prev) => {
      const arr = prev[key];
      return {
        ...prev,
        [key]: arr.includes(value)
          ? arr.filter((v) => v !== value)
          : [...arr, value],
      };
    });
  };

  const clearFilters = () => {
    setFilters({ status: [], docType: [], sourceType: [] });
  };

  const handleDelete = async (doc: DocumentRecord) => {
    if (!confirm(`确定删除 "${doc.filename}"？`)) return;
    try {
      await deleteDoc.mutateAsync(doc.id);
      toast.success("已删除");
    } catch {
      toast.error("删除失败");
    }
  };

  const handleReindex = async (doc: DocumentRecord) => {
    try {
      await reindex.mutateAsync(doc.id);
      toast.success("重建索引成功");
    } catch {
      toast.error("重建索引失败");
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="p-3">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="搜索文档..."
              value={keyword}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setKeyword(e.target.value)
              }
              className="h-8 text-sm pl-9 pr-9"
            />
            {keyword && (
              <button
                onClick={() => setKeyword("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger className="h-8 px-2 rounded-md border bg-background hover:bg-accent relative">
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
                  {filterOptions.status.map((s) => (
                    <DropdownMenuCheckboxItem
                      key={s}
                      checked={filters.status.includes(s)}
                      onCheckedChange={() => toggleFilter("status", s)}
                    >
                      {s === "completed"
                        ? "已完成"
                        : s === "processing"
                          ? "处理中"
                          : s === "failed"
                            ? "失败"
                            : s}
                    </DropdownMenuCheckboxItem>
                  ))}
                </DropdownMenuGroup>
              )}
              {filterOptions.status.length > 0 &&
                (filterOptions.docType.length > 0 ||
                  filterOptions.sourceType.length > 0) && (
                  <DropdownMenuSeparator />
                )}
              {filterOptions.docType.length > 0 && (
                <DropdownMenuGroup>
                  <DropdownMenuLabel>文档类型</DropdownMenuLabel>
                  {filterOptions.docType.map((t) => (
                    <DropdownMenuCheckboxItem
                      key={t}
                      checked={filters.docType.includes(t)}
                      onCheckedChange={() => toggleFilter("docType", t)}
                    >
                      {t}
                    </DropdownMenuCheckboxItem>
                  ))}
                </DropdownMenuGroup>
              )}
              {filterOptions.docType.length > 0 &&
                filterOptions.sourceType.length > 0 && (
                  <DropdownMenuSeparator />
                )}
              {filterOptions.sourceType.length > 0 && (
                <DropdownMenuGroup>
                  <DropdownMenuLabel>来源</DropdownMenuLabel>
                  {filterOptions.sourceType.map((s) => (
                    <DropdownMenuCheckboxItem
                      key={s}
                      checked={filters.sourceType.includes(s)}
                      onCheckedChange={() => toggleFilter("sourceType", s)}
                    >
                      {s === "file" ? "文件上传" : s === "url" ? "URL 抓取" : s}
                    </DropdownMenuCheckboxItem>
                  ))}
                </DropdownMenuGroup>
              )}
              {activeFilterCount > 0 && (
                <button
                  onClick={clearFilters}
                  className="w-full px-2 py-1.5 text-sm text-muted-foreground hover:text-foreground text-left"
                >
                  清除筛选
                </button>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      <Separator />
      <ScrollArea className="flex-1 min-h-0 px-3 py-2">
        {isLoading ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            加载中...
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            暂无文档
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((doc: DocumentRecord) => (
              <DocCard
                key={doc.id}
                doc={doc}
                selected={selectedId === doc.id}
                onSelect={() => onSelectDoc(doc.id, doc.filename)}
                onDelete={() => handleDelete(doc)}
                onReindex={() => handleReindex(doc)}
              />
            ))}
          </div>
        )}
      </ScrollArea>
      <Separator />
      <div className="p-3">
        <UploadZone />
      </div>
    </div>
  );
}
