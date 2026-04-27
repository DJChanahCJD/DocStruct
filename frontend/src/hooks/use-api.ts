import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ACTIVE_DOCUMENT_STATUSES,
  deleteDocument,
  getDocumentChunks,
  getDocumentFile,
  getDocument,
  listDocuments,
  retryExtraction,
  updateDocument,
  uploadFile,
  type DocumentFilePayload,
  type DocumentChunksResponse,
  type UpdateDocumentRequest,
} from "@/lib/api";

const activeDocumentStatuses = new Set<string>(ACTIVE_DOCUMENT_STATUSES);

export function useDocuments() {
  return useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    refetchInterval: (query) => {
      const docs = query.state.data ?? [];
      return docs.some((doc) => activeDocumentStatuses.has(doc.status)) ? 2000 : false;
    },
  });
}

export function useDocument(id: number | null) {
  return useQuery({
    queryKey: ["document", id],
    queryFn: () => getDocument(id!),
    enabled: id !== null,
    refetchInterval: (query) => {
      const doc = query.state.data;
      if (!doc) {
        return false;
      }
      return activeDocumentStatuses.has(doc.status) ? 2000 : false;
    },
  });
}

export function useDocumentFile(id: number | null) {
  return useQuery<DocumentFilePayload>({
    queryKey: ["document-file", id],
    queryFn: () => getDocumentFile(id!),
    enabled: id !== null,
    staleTime: Infinity,
  });
}

export function useDocumentChunks(id: number | null) {
  return useQuery<DocumentChunksResponse>({
    queryKey: ["document-chunks", id],
    queryFn: () => getDocumentChunks(id!),
    enabled: id !== null,
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.removeQueries({ queryKey: ["document", id] });
      qc.removeQueries({ queryKey: ["document-chunks", id] });
    },
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: uploadFile,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export function useUpdateDocument(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: UpdateDocumentRequest) => updateDocument(id, req),
    onSuccess: (document) => {
      qc.setQueryData(["document", id], document);
      qc.invalidateQueries({ queryKey: ["document-chunks", id] });
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

export function useRetryExtraction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: retryExtraction,
    onSuccess: (document) => {
      qc.setQueryData(["document", document.id], document);
      qc.invalidateQueries({ queryKey: ["document-chunks", document.id] });
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}
