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
  polish?: string;
  note?: string;
  mindmap?: string;
  brainstorm?: string;
}

/** A complete transcription record (immutable — create new objects to update). */
export interface TranscriptRecord {
  id: string;
  title: string;
  audio_path: string | null;
  transcript: string;
  segments: Segment[];
  ai_results: AiResults;
  category: string;
  tags: string[];
  duration_seconds: number;
  created_at: string;
  updated_at: string;
  version: number;
}

/** A version snapshot for history tracking. */
export interface Version {
  record_id: string;
  version: number;
  transcript: string;
  ai_results: AiResults;
  created_at: string;
}

/** AI model configuration. */
export interface AiConfig {
  provider: "openai" | "anthropic" | "ollama" | "qwen";
  model: string;
  api_key: string | null;
  base_url: string | null;
  temperature: number;
  max_tokens: number;
}

/** ASR engine configuration. */
export interface AsrConfig {
  model_dir: string;
  language: "zh" | "en" | "auto";
  sample_rate: number;
  use_gpu: boolean;
  active_streaming_model: string;
  active_offline_model: string;
  auto_punctuate: boolean;
  download_source: string;
  custom_ghproxy_domain: string | null;
  proxy_mode: string;
  proxy_url: string | null;
}

/** AI processing modes. */
export type AiMode = "polish" | "note" | "mindmap" | "brainstorm";

/** Export file formats. */
export type ExportFormat = "md" | "txt" | "docx" | "srt";

/** List filter options. */
export interface RecordFilter {
  category?: string;
  keyword?: string;
  sort_by?: "created_at" | "updated_at" | "title";
  sort_order?: "asc" | "desc";
}

/** Model entry from the registry catalog. */
export interface ModelEntry {
  model_id: string;
  display_name: string;
  model_type: "streaming" | "offline" | "vad";
  languages: string[];
  size_mb: number;
  description: string;
}

/** An installed model on disk. */
export interface InstalledModel {
  model_id: string;
  valid: boolean;
  size_mb: number;
}

/** Download progress event payload. */
export interface DownloadProgress {
  model_id: string;
  phase: "download" | "extract" | "validate";
  percent: number;
  bytes_downloaded?: number;
  total_bytes?: number;
}
