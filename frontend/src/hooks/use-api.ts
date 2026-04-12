import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listDocuments,
  getDocument,
  deleteDocument,
  uploadFile,
  uploadUrl,
  reindexDocument,
  askQuestion,
  type QaRequest,
  type QaResponse,
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

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: uploadFile,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export function useUploadUrl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: uploadUrl,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export function useReindex() {
  return useMutation({
    mutationFn: reindexDocument,
  });
}

export function useAskQuestion() {
  return useMutation({
    mutationFn: (req: QaRequest) => askQuestion(req),
  });
}

export type { QaResponse };
