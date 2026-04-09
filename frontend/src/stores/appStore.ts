import { defineStore } from "pinia";
import { ref } from "vue";
import type { TranscriptRecord, AiConfig, AsrConfig } from "../types";

/** A single toast notification entry. */
export interface Toast {
  id: string;
  message: string;
  type: "success" | "error" | "warning" | "info";
}

let toastIdCounter = 0;

export const useAppStore = defineStore("app", () => {
  /* ---- bridge ready state ---- */
  const ready = ref(false);

  /* ---- dark mode ---- */
  const darkMode = ref(
    localStorage.getItem("theme") === "sherpanote-dark",
  );

  function toggleDarkMode() {
    darkMode.value = !darkMode.value;
    const theme = darkMode.value ? "sherpanote-dark" : "sherpanote-light";
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }

  /** Apply persisted theme on app start. */
  function applyTheme() {
    const theme = darkMode.value ? "sherpanote-dark" : "sherpanote-light";
    document.documentElement.setAttribute("data-theme", theme);
  }

  /* ---- records cache ---- */
  const records = ref<TranscriptRecord[]>([]);
  const currentRecord = ref<TranscriptRecord | null>(null);

  /* ---- processing states ---- */
  const isRecording = ref(false);
  const isTranscribing = ref(false);
  const transcribeProgress = ref(0);
  const isAiProcessing = ref(false);

  /* ---- AI config ---- */
  const aiConfig = ref<AiConfig>({
    provider: "openai",
    model: "gpt-4o-mini",
    api_key: null,
    base_url: null,
    temperature: 0.7,
    max_tokens: 8192,
  });

  /* ---- Auto AI processing modes ---- */
  const autoAiModes = ref<string[]>([]);

  /* ---- ASR config ---- */
  const asrConfig = ref<AsrConfig>({
    model_dir: "",
    language: "auto",
    sample_rate: 16000,
    use_gpu: false,
    active_streaming_model: "",
    active_offline_model: "",
    auto_punctuate: false,
    download_source: "github",
    custom_ghproxy_domain: null,
    proxy_mode: "none",
    proxy_url: null,
  });

  /* ---- toast notifications ---- */
  const toasts = ref<Toast[]>([]);

  function showToast(message: string, type: Toast["type"] = "info") {
    const id = `toast-${++toastIdCounter}`;
    const toast: Toast = { id, message, type };
    toasts.value = [...toasts.value, toast];
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id);
    }, 3000);
  }

  /* ---- audio sync ---- */
  const activeSegmentIndex = ref(-1);

  return {
    ready,
    darkMode,
    toggleDarkMode,
    applyTheme,
    records,
    currentRecord,
    isRecording,
    isTranscribing,
    transcribeProgress,
    isAiProcessing,
    aiConfig,
    asrConfig,
    autoAiModes,
    toasts,
    showToast,
    activeSegmentIndex,
  };
});
