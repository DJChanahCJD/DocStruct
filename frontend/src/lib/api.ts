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

export interface UpdateDocumentRequest {
  parsed_content?: string;
  extracted_data?: Record<string, unknown>;
}

export interface ReviewField {
  node_id: string;
  field_key: string;
  label: string;
  value: unknown;
  value_type: string;
  editable: boolean;
}

export interface ReviewItem {
  node_id: string;
  title: string;
  summary?: string | null;
  order: number;
  fields: ReviewField[];
}

export interface ReviewGroup {
  group_key: string;
  label: string;
  item_type: string;
  items: ReviewItem[];
}

export interface DocumentReviewModel {
  doc_type: string;
  meta_fields: ReviewField[];
  groups: ReviewGroup[];
}

export interface ReviewChange {
  node_id: string;
  field_key: string;
  value: unknown;
}

export interface ReviewNode {
  node_id: string;
  node_type: "meta" | "item";
  label: string;
  group_key?: string | null;
  title: string;
  fields: ReviewField[];
}

export interface ReviewModelUpdateRequest {
  changes: ReviewChange[];
  reindex?: boolean;
}

export interface ReviewModelUpdateResponse {
  document: DocumentRecord;
  review_model: DocumentReviewModel;
  warning?: string | null;
}

export interface ReviewModelReExtractRequest {
  node_id: string;
  instruction?: string;
  use_rag?: boolean;
}

export interface ReviewModelReExtractResponse {
  node: ReviewNode;
}

export interface DocumentSourceMeta {
  source_type: string;
  filename: string;
  mime_type: string;
  preview_mode: "pdf" | "office" | "text" | "external_url" | "unsupported";
  download_url: string;
  raw_text_available: boolean;
  source_url: string | null;
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
  doc_type: string;
  llm_model?: string | null;
}

export interface UploadUrlRequest {
  url: string;
  doc_type: string;
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
  doc_ids?: number[] | null;
  top_k?: number;
  llm_model?: string | null;
}

export interface QaResponse {
  answer: string;
  citations: CitationItem[];
}

export interface ReExtractRequest {
  scope: "full" | "field";
  field_key?: string;
  instruction?: string;
}

export interface ReExtractResponse {
  result: Record<string, unknown>;
  scope: "full" | "field";
  field_key?: string | null;
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

export async function getDocumentSourceMeta(id: number): Promise<DocumentSourceMeta> {
  const { data } = await api.get<DocumentSourceMeta>(`/documents/${id}/source-meta`);
  return data;
}

export async function updateDocument(
  id: number,
  req: UpdateDocumentRequest,
): Promise<DocumentRecord> {
  const { data } = await api.patch<DocumentRecord>(`/documents/${id}`, req);
  return data;
}

export async function getReviewModel(id: number): Promise<DocumentReviewModel> {
  const { data } = await api.get<DocumentReviewModel>(`/documents/${id}/review-model`);
  return data;
}

export async function updateReviewModel(
  id: number,
  req: ReviewModelUpdateRequest,
): Promise<ReviewModelUpdateResponse> {
  const { data } = await api.patch<ReviewModelUpdateResponse>(`/documents/${id}/review-model`, req);
  return data;
}

export async function reExtractReviewNode(
  id: number,
  req: ReviewModelReExtractRequest,
): Promise<ReviewModelReExtractResponse> {
  const { data } = await api.post<ReviewModelReExtractResponse>(
    `/documents/${id}/review-model/re-extract`,
    req,
  );
  return data;
}

export async function deleteDocument(id: number): Promise<void> {
  await api.delete(`/documents/${id}`);
}

export async function uploadFile(req: UploadFileRequest): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", req.file);
  form.append("doc_type", req.doc_type);
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

export async function reExtractDocument(
  id: number,
  req: ReExtractRequest,
): Promise<ReExtractResponse> {
  const { data } = await api.post<ReExtractResponse>(`/documents/${id}/re-extract`, req);
  return data;
}
