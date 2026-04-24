import axios from "axios";

const api = axios.create({
  baseURL: "/api",
});

export const ACTIVE_DOCUMENT_STATUSES = ["pending", "uploaded", "parsing", "extracting"] as const;

export interface DocumentRecord {
  id: number;
  filename: string;
  stored_path: string;
  upload_time: string;
  doc_type: string;
  parsed_content: string | null;
  extracted_data: Record<string, unknown> | null;
  status: string;
  error_message: string | null;
}

export interface UpdateDocumentRequest {
  parsed_content?: string;
  extracted_data?: Record<string, unknown>;
}

export interface UploadResponse {
  id: number;
  filename: string;
  status: string;
  message: string;
}

export interface UploadFileRequest {
  file: File;
  doc_type: string;
}

export interface DocumentFilePayload {
  blob: Blob;
  contentType: string;
  fileName: string;
}

export async function listDocuments(): Promise<DocumentRecord[]> {
  const { data } = await api.get<DocumentRecord[]>("/documents");
  return data;
}

export async function getDocument(id: number): Promise<DocumentRecord> {
  const { data } = await api.get<DocumentRecord>(`/documents/${id}`);
  return data;
}

export async function updateDocument(
  id: number,
  req: UpdateDocumentRequest,
): Promise<DocumentRecord> {
  const { data } = await api.patch<DocumentRecord>(`/documents/${id}`, req);
  return data;
}

export async function deleteDocument(id: number): Promise<void> {
  await api.delete(`/documents/${id}`);
}

export async function uploadFile(req: UploadFileRequest): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", req.file);
  form.append("doc_type", req.doc_type);
  const { data } = await api.post<UploadResponse>("/upload", form);
  return data;
}

export async function getDocumentFile(id: number): Promise<DocumentFilePayload> {
  const response = await api.get<Blob>(`/documents/${id}/file`, {
    responseType: "blob",
  });
  const disposition = response.headers["content-disposition"] as string | undefined;
  const fileNameMatch = disposition?.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);
  const fileName = fileNameMatch?.[1]
    ? decodeURIComponent(fileNameMatch[1].replace(/"/g, ""))
    : `document-${id}`;

  return {
    blob: response.data,
    contentType: response.headers["content-type"] ?? response.data.type ?? "",
    fileName,
  };
}

export async function retryExtraction(id: number): Promise<DocumentRecord> {
  const { data } = await api.post<DocumentRecord>(`/documents/${id}/retry-extraction`);
  return data;
}
