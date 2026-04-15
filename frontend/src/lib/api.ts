import axios from "axios";

const api = axios.create({
  baseURL: "/api",
});

// ============ Types ============

export interface DocumentRecord {
  id: number;
  filename: string;
  stored_path: string;
  upload_time: string;
  doc_type: string;
  source_type: string;
  source_url: string | null;
  llm_model: string | null;
  parsed_content: string | null;
  extracted_data: Record<string, unknown> | null;
  status: string;
  error_message: string | null;
}

export interface UploadResponse {
  id: number;
  filename: string;
  status: string;
  message: string;
}

export interface TextModelOption {
  id: string;
  label: string;
  description: string;
  is_default: boolean;
}

export interface TextModelListResponse {
  models: TextModelOption[];
}

export interface UploadFileRequest {
  file: File;
  llm_model?: string | null;
}

export interface UploadUrlRequest {
  url: string;
  llm_model?: string | null;
}

export interface CitationItem {
  doc_id: number;
  chunk_id: number;
  score: number;
  snippet: string;
  title_path?: string;
}

export interface QaRequest {
  question: string;
  doc_id?: number | null;
  top_k?: number;
  llm_model?: string | null;
}

export interface QaResponse {
  answer: string;
  citations: CitationItem[];
}

// ============ API Functions ============

export async function listDocuments(): Promise<DocumentRecord[]> {
  const { data } = await api.get<DocumentRecord[]>("/documents");
  return data;
}

export async function listTextModels(): Promise<TextModelListResponse> {
  const { data } = await api.get<TextModelListResponse>("/text-models");
  return data;
}

export async function getDocument(id: number): Promise<DocumentRecord> {
  const { data } = await api.get<DocumentRecord>(`/documents/${id}`);
  return data;
}

export async function deleteDocument(id: number): Promise<void> {
  await api.delete(`/documents/${id}`);
}

export async function uploadFile(req: UploadFileRequest): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", req.file);
  if (req.llm_model) {
    form.append("llm_model", req.llm_model);
  }
  const { data } = await api.post<UploadResponse>("/upload", form);
  return data;
}

export async function uploadUrl(req: UploadUrlRequest): Promise<UploadResponse> {
  const { data } = await api.post<UploadResponse>("/upload/url", req);
  return data;
}

export async function reindexDocument(id: number): Promise<void> {
  await api.post(`/reindex/${id}`);
}

export async function askQuestion(req: QaRequest): Promise<QaResponse> {
  const { data } = await api.post<QaResponse>("/qa", req);
  return data;
}

