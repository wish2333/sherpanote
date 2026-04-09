/** Shared type definitions for SherpaNote frontend. */

export interface Segment {
  index: number;
  text: string;
  start_time: number;
  end_time: number;
  speaker: string | null;
  is_final: boolean;
}

export interface TranscriptRecord {
  id: string;
  title: string;
  audio_path: string | null;
  can_retranscribe?: boolean;
  transcript: string;
  segments: Segment[];
  ai_results: Record<string, string>;
  category: string;
  tags: string[];
  duration_seconds: number;
  created_at: string;
  updated_at: string;
  version?: number;
}

export interface AiConfig {
  provider: string;
  model: string;
  api_key: string | null;
  base_url: string | null;
  temperature: number;
  max_tokens: number;
}

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

export interface AsrConfig {
  model_dir: string;
  language: string;
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

export interface AppSettings {
  ai: AiConfig;
  asr: AsrConfig;
  auto_ai_modes: string[];
  max_tokens_mode: string;  // "auto" | "custom" | "default"
}

export type AiMode = "polish" | "note" | "mindmap" | "brainstorm" | `preset_${string}`;

export type AiResults = Record<string, string>;

export type ExportFormat = "txt" | "md" | "srt" | "docx";

export interface RecordFilter {
  keyword?: string;
  category?: string;
  sort_by?: string;
  sort_order?: string;
}

export interface Version {
  record_id: string;
  version: number;
  transcript: string;
  ai_results_json: string;
  created_at: string;
}

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

export interface DownloadProgress {
  model_id: string;
  status: string;
  percent: number;
  downloaded_mb: number;
  total_mb: number;
  error?: string;
}
