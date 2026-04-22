import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteDocument,
  getDocumentFile,
  getDocument,
  listDocuments,
  updateDocument,
  uploadFile,
  type DocumentFilePayload,
  type UpdateDocumentRequest,
} from "@/lib/api";

export function useDocuments() {
  return useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
  });
}

export function useDocument(id: number | null) {
  return useQuery({
    queryKey: ["document", id],
    queryFn: () => getDocument(id!),
    enabled: id !== null,
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

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.removeQueries({ queryKey: ["document", id] });
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
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}
