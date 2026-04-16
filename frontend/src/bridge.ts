/** Core bridge functions for communicating with the Python backend. */
import type { GpuStatus, WhisperBinaryStatus, ModelEntry, InstalledModel, DependencyStatus } from "./types";

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}

function getRawApi(): PyWebViewApi {
  const pw = window.pywebview;
  if (!pw || !pw.api) {
    throw new Error("pywebview API not available. Wait for pywebview to initialize.");
  }
  return pw.api;
}

/**
 * Poll until the pywebview bridge is ready.
 * Returns a promise that resolves when ``window.pywebview.api`` is populated.
 */
export function waitForPyWebView(timeout = 10_000): Promise<void> {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      if (window.pywebview?.api) {
        resolve();
        return;
      }
      if (Date.now() - start > timeout) {
        reject(new Error("pywebview bridge did not initialize within timeout"));
        return;
      }
      setTimeout(check, 50);
    };
    check();
  });
}

/**
 * Call an ``@expose``-decorated Python method and return the typed result.
 *
 * ```ts
 * const res = await call<string[]>("get_items")
 * if (res.success) console.log(res.data)
 * ```
 */
export async function call<T = unknown>(
  method: string,
  ...args: unknown[]
): Promise<ApiResponse<T>> {
  const api = getRawApi();
  if (!(method in api)) {
    return { success: false, error: `Method '${method}' not found on bridge` };
  }
  return (await api[method](...args)) as ApiResponse<T>;
}

/**
 * Listen for events dispatched by ``Bridge._emit()`` from the Python side.
 *
 * Event names are prefixed with ``pywebvue:``. Returns a cleanup function
 * that removes the listener.
 *
 * ```ts
 * const off = onEvent<{ percent: number }>("progress", (detail) => {
 *   console.log(detail.percent)
 * })
 * // later:
 * off()
 * ```
 */
export function onEvent<T = unknown>(
  name: string,
  handler: (detail: T) => void,
): () => void {
  const event = `pywebvue:${name}`;
  const listener = (e: Event) => {
    handler((e as CustomEvent).detail);
  };
  window.addEventListener(event, listener);
  return () => window.removeEventListener(event, listener);
}

// ------------------------------------------------------------------ //
//  Model management API helpers                                       //
// ------------------------------------------------------------------ //

export function listAvailableModels(modelType?: string) {
  return call<ModelEntry[]>("list_available_models", modelType ?? null);
}

export function listInstalledModels() {
  return call<InstalledModel[]>("list_installed_models");
}

export function installModel(modelId: string) {
  return call("install_model", modelId);
}

export function deleteModel(modelId: string) {
  return call("delete_model", modelId);
}

export function cancelModelInstall() {
  return call("cancel_model_install");
}

export function pickDirectory() {
  return call<{ path: string }>("pick_directory");
}

export function pickFile(fileTypes?: string[]) {
  return call<{ path: string }>("pick_file", fileTypes || ["All Files (*.*)"]);
}

export function validateModel(modelId: string) {
  return call<{ valid: boolean; missing?: string[] }>("validate_model", modelId);
}

export function getDownloadLinks(modelId: string) {
  return call<Array<{ label: string; url: string }>>("get_download_links", modelId);
}

// ------------------------------------------------------------------ //
//  GPU detection API helper                                          //
// ------------------------------------------------------------------ //

export function detectGpu() {
  return call<GpuStatus>("detect_gpu");
}

// ------------------------------------------------------------------ //
//  whisper.cpp binary management API helpers                        //
// ------------------------------------------------------------------ //

export function getWhisperBinaryStatus() {
  return call<WhisperBinaryStatus>("get_whisper_binary_status");
}

export function installWhisperBinary(variant?: string) {
  return call<{ variant?: string; version?: string; switched?: boolean; source?: string }>("install_whisper_binary", variant ?? null);
}

export function uninstallWhisperBinary() {
  return call("uninstall_whisper_binary");
}

// ------------------------------------------------------------------ //
//  Transcription and Download API helpers                               //
// ------------------------------------------------------------------ //

export function downloadAndTranscribe(url: string) {
  return call<{ status: string }>("download_and_transcribe", url);
}

// ------------------------------------------------------------------ //
//  Dependency Management helpers                                       //
// ------------------------------------------------------------------ //

export function getDependencyStatus() {
  return call<DependencyStatus>("get_dependency_status");
}

export function installStaticFfmpeg() {
  return call<{ path: string; source: string }>("install_static_ffmpeg");
}

// ------------------------------------------------------------------ //
//  Backup / Restore API helpers                                      //
// ------------------------------------------------------------------ //

export interface BackupOptions {
  include_config: boolean;
  include_presets: boolean;
  include_records: boolean;
  include_versions: boolean;
  include_audio: boolean;
}

export interface BackupSummary {
  backup_version: number;
  source_platform: string;
  created_at: string;
  config?: boolean;
  ai_presets?: number;
  processing_presets?: number;
  records?: number;
  versions?: number;
  audio_files?: number;
}

export function exportBackup(path: string, options: BackupOptions) {
  return call<{ path: string }>("export_backup", path, options);
}

export function importBackup(path: string) {
  return call<BackupSummary>("import_backup", path);
}
