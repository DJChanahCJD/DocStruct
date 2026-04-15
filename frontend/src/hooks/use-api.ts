import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  askQuestion,
  deleteDocument,
  getDocument,
  listDocuments,
  listTextModels,
  reExtractDocument,
  reindexDocument,
  updateDocument,
  uploadFile,
  uploadUrl,
  type QaRequest,
  type QaResponse,
  type ReExtractRequest,
  type UpdateDocumentRequest,
} from "@/lib/api";

/**
 * 获取文档列表。
 */
export function useDocuments() {
  return useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
  });
}

/**
 * 获取可用文本模型列表。
 */
export function useTextModels() {
  return useQuery({
    queryKey: ["text-models"],
    queryFn: listTextModels,
    staleTime: Infinity,
  });
}

/**
 * 获取单篇文档详情。
 */
export function useDocument(id: number | null) {
  return useQuery({
    queryKey: ["document", id],
    queryFn: () => getDocument(id!),
    enabled: id !== null,
  });
}

/**
 * 删除文档并刷新列表。
 */
export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

/**
 * 上传文件并刷新列表。
 */
export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: uploadFile,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

/**
 * 上传 URL 并刷新列表。
 */
export function useUploadUrl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: uploadUrl,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

/**
 * 更新文档的结构化 JSON 数据（extracted_data），并刷新列表和详情缓存。
 */
export function useUpdateDocument(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: UpdateDocumentRequest) => updateDocument(id, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["document", id] });
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

/**
 * 触发文档重建索引。
 */
export function useReindex() {
  return useMutation({
    mutationFn: reindexDocument,
  });
}

/**
 * 发起问答请求。
 */
export function useAskQuestion() {
  return useMutation({
    mutationFn: (req: QaRequest) => askQuestion(req),
  });
}

/**
 * 对已有文档发起重新提取，结果不持久化，由调用方决定是否保存。
 */
export function useReExtract(docId: number) {
  return useMutation({
    mutationFn: (req: ReExtractRequest) => reExtractDocument(docId, req),
  });
}

export type { QaResponse };

