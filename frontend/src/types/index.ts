/**
 * SherpaNote shared type definitions.
 *
 * These types mirror the Python dataclasses defined in py/ modules.
 * Keep them in sync when modifying backend data structures.
 */

/** A single transcript segment with timestamp, used for audio sync. */
export interface Segment {
  index: number;
  text: string;
  start_time: number;
  end_time: number;
  speaker: string | null;
  is_final: boolean;
}

/** AI processing result keyed by mode name. */
export interface AiResults {
  [mode: string]: string | undefined;
}

/** A complete transcription record (immutable -- create new objects to update). */
export interface TranscriptRecord {
  id: string;
  title: string;
  audio_path: string | null;
  can_retranscribe?: boolean;
  has_ai?: number;
  transcript: string;
  segments: Segment[];
  ai_results: AiResults;
  category: string;
  tags: string[];
  duration_seconds: number;
  created_at: string;
  updated_at: string;
  version?: number;
}

/** A version snapshot for history tracking. */
export interface Version {
  record_id: string;
  version: number;
  transcript: string;
  segments: Segment[];
  ai_results: AiResults;
  created_at: string;
}

/** AI model configuration. */
export interface AiConfig {
  provider: string;
  model: string;
  api_key: string | null;
  base_url: string | null;
  temperature: number;
  max_tokens: number;
}

/** AI provider preset. */
export interface AiPreset {
  id: string;
  name: string;
  provider: string;
  model: string;
  api_key: string | null;
  base_url: string | null;
  temperature: number;
  max_tokens: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** AI processing preset. */
export interface AiProcessingPreset {
  id: string;
  name: string;
  mode: string;
  prompt: string;
  is_default: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

/** ASR engine configuration. */
export interface AsrConfig {
  model_dir: string;
  language: string;
  sample_rate: number;
  use_gpu: boolean;
  asr_backend: string;
  active_streaming_model: string;
  active_offline_model: string;
  active_whisper_model: string;
  auto_punctuate: boolean;
  download_source: string;
  custom_ghproxy_domain: string | null;
  proxy_mode: string;
  proxy_url: string | null;
  vad_min_silence_duration: number;
  vad_min_speech_duration: number;
  vad_max_speech_duration: number;
  vad_threshold: number;
  offline_use_vad: boolean;
  vad_padding: number;
  active_vad_model: string;
  ytdlp_cookie_path: string;
  ffmpeg_path: string;
}

/** OCR engine configuration. Each role independently picks version and type. */
export interface OcrConfig {
  det_model_version: "v4" | "v5";
  det_model_type: "mobile" | "server";
  rec_model_version: "v4" | "v5";
  rec_model_type: "mobile" | "server";
  cls_model_version: "v4" | "v5";
  cls_model_type: "mobile" | "server";
}

/** OCR model file info from scan. */
export interface OcrModelFileInfo {
  version: string;
  role: "det" | "rec" | "cls";
  model_type: "mobile" | "server";
  filename: string;
  size_mb: number;
  downloaded: boolean;
}

/** OCR processing mode. */
export type OcrMode = "single" | "batch" | "sequential";

/** File entry in OCR upload list. */
export interface OcrFileEntry {
  path: string;
  name: string;
  type: "image" | "pdf" | "office";
  size_mb: number;
  page_count?: number;
}

/** Plugin system configuration. */
export interface PluginConfig {
  manual_java_path: string | null;
  docling_artifacts_path: string | null;
}

/** Document extraction backend selection. */
export interface DocumentConfig {
  text_pdf_engine: "markitdown" | "opendataloader" | "docling" | "ppocr";
  scan_pdf_engine: "ppocr" | "docling";
}

/** Plugin package installation status. */
export interface PluginPackageStatus {
  name: string;
  installed: boolean;
  version: string | null;
}

/** Java runtime detection result. */
export interface JavaDetectionResult {
  found: boolean;
  path: string | null;
  version: string | null;
  error: string | null;
}

/** App settings bundle. */
export interface AppSettings {
  ai: AiConfig;
  asr: AsrConfig;
  ocr: OcrConfig;
  plugin: PluginConfig;
  document: DocumentConfig;
  auto_ai_modes: string[];
  max_tokens_mode: string;
}

/** AI processing modes. */
export type AiMode = "polish" | "note" | "mindmap" | "brainstorm" | `preset_${string}`;

export type ExportFormat = "txt" | "md" | "srt" | "docx";

/** List filter options. */
export interface RecordFilter {
  keyword?: string;
  category?: string;
  sort_by?: string;
  sort_order?: string;
}

/** Model entry from the registry catalog. */
export interface ModelEntry {
  model_id: string;
  display_name: string;
  model_type: string;
  languages: string[];
  size_mb: number;
  description: string;
  sources: string[];
  manual_download_links: Array<{ label: string; url: string }>;
}

/** An installed model on disk. */
export interface InstalledModel {
  model_id: string;
  model_type: string;
  display_name: string;
  path: string;
  validated: boolean;
  valid: boolean;
  missing_files: string[];
  size_mb: number;
}

/** Download progress event payload. */
export interface DownloadProgress {
  model_id: string;
  status: string;
  percent: number;
  downloaded_mb: number;
  total_mb: number;
  error?: string;
}

/** GPU detection result from the backend. */
export interface GpuStatus {
  available: boolean;
  gpu_name: string;
  cuda_version: string;
  reason: string;
  onnx_provider: string;
}

/** whisper.cpp binary installation status. */
export interface WhisperBinaryStatus {
  installed: boolean;
  version: string | null;
  platform: string;
  available_variants: string[];
  default_variant: string | null;
  current_variant?: string | null;
  installed_variants?: string[];
  source?: string;
}

export interface DependencyStatus {
  ffmpeg: { installed: boolean; source: string; path: string };
  ytdlp: { installed: boolean; version: string };
}
