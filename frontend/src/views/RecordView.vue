<script setup lang="ts">
/**
 * RecordView - Live recording and file upload transcription page.
 *
 * Two modes:
 * 1. Microphone streaming: captures audio via Web Audio API,
 *    sends Base64 PCM chunks to Python backend via Bridge.
 * 2. File upload: drag-and-drop or select an audio file for
 *    offline transcription.
 *
 * Uses AudioRecorder, TranscriptPanel, useRecording, useTranscript.
 */
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useRecording } from "../composables/useRecording";
import { useTranscript } from "../composables/useTranscript";
import { call, onEvent, listAvailableModels, listInstalledModels } from "../bridge";
import { useAppStore } from "../stores/appStore";
import type { ModelEntry, InstalledModel, AsrConfig } from "../types";
import AudioRecorder from "../components/AudioRecorder.vue";
import TranscriptPanel from "../components/TranscriptPanel.vue";

const router = useRouter();
const route = useRoute();
const store = useAppStore();

const {
  isRecording,
  isLoadingModel,
} = useRecording();

const {
  partialText,
  finalSegments,
  isTranscribingFile,
  startListening,
  stopListening,
  resetState,
  transcribeFile,
  saveAsRecord,
} = useTranscript();

// ---- Quick settings state ----
const availableModels = ref<ModelEntry[]>([]);
const installedModels = ref<InstalledModel[]>([]);

const languages = [
  { value: "auto", label: "自动检测" },
  { value: "zh", label: "中文" },
  { value: "en", label: "英语" },
  { value: "ja", label: "日语" },
  { value: "ko", label: "韩语" },
  { value: "yue", label: "粤语" },
  { value: "de", label: "德语" },
  { value: "fr", label: "法语" },
  { value: "es", label: "西班牙语" },
  { value: "ru", label: "俄语" },
  { value: "it", label: "意大利语" },
  { value: "pt", label: "葡萄牙语" },
];

const installedStreamingModels = computed(() =>
  installedModels.value.filter(
    (m) =>
      m.model_type === "streaming" ||
      // SenseVoice and Qwen3-ASR models support simulated streaming via VAD + offline recognizer.
      m.model_id.includes("sense-voice") || m.model_id.includes("sensevoice") ||
      m.model_id.includes("qwen3-asr"),
  ),
);

const installedOfflineModels = computed(() =>
  installedModels.value.filter((m) => m.model_type === "offline"),
);

const installedWhisperModels = computed(() =>
  installedModels.value.filter((m) => m.model_type === "whispercpp"),
);

function displayName(modelId: string): string {
  return availableModels.value.find((m) => m.model_id === modelId)?.display_name ?? modelId;
}

async function loadModels() {
  const [availRes, instRes] = await Promise.all([
    listAvailableModels(),
    listInstalledModels(),
  ]);
  if (availRes.success && availRes.data) {
    availableModels.value = availRes.data;
  }
  if (instRes.success && instRes.data) {
    installedModels.value = instRes.data;
  }
}

async function loadAsrConfig() {
  const res = await call<{ asr: AsrConfig }>("get_config");
  if (res.success && res.data?.asr) {
    store.asrConfig = res.data.asr;
  }
}

async function saveQuickSetting() {
  await call("update_config", {
    ai: store.aiConfig,
    asr: store.asrConfig,
    auto_ai_modes: store.autoAiModes,
  });
}

// ---- Recording callbacks ----

async function handleRecordingComplete(data: { text: string; segments: { text: string; timestamp: number[] }[]; duration: number; audio_path: string | null }) {
  stopListening();
  const record = await saveAsRecord(
    `Recording ${new Date().toLocaleString("zh-CN")}`,
    data.text,
    data.segments,
    data.audio_path,
    data.duration,
  );
  if (record) {
    router.push(`/editor/${record.id}`);
  }
}

async function handleFileSelected(filePath: string) {
  const result = await transcribeFile(filePath);
  if (result) {
    const record = await saveAsRecord(
      filePath.split("/").pop()?.split("\\").pop() || "Imported",
      result.text,
      result.segments,
      filePath,
    );
    if (record) {
      router.push(`/editor/${record.id}`);
    }
  }
}

// Import & Transcribe: copy file into data/audio/ first, then transcribe.
const isImporting = ref(false);
const importProgress = ref(0);

// Video Download & Transcribe
const downloadUrl = ref("");
const isDownloading = ref(false);
const downloadProgress = ref(0);

async function handleImportAndTranscribe() {
  const res = await call<string[]>("pick_audio_file");
  if (!res.success || !res.data || res.data.length === 0) return;
  await startImportTranscribe(res.data[0]);
}

async function startImportTranscribe(filePath: string) {
  isImporting.value = true;
  importProgress.value = 0;

  // Listen for progress during import transcription.
  const offProgress = onEvent<{ percent: number }>(
    "transcribe_progress",
    ({ percent }) => {
      importProgress.value = percent;
    },
  );

  const startRes = await call("import_and_transcribe", filePath);
  if (!startRes.success) {
    isImporting.value = false;
    offProgress();
    store.showToast(startRes.error ?? "Failed to start import", "error");
    return;
  }

  // Wait for completion.
  await new Promise<void>((resolve) => {
    const offComplete = onEvent<{ record_id: string }>(
      "import_transcribe_complete",
      (detail) => {
        offComplete();
        offProgress();
        isImporting.value = false;
        router.push(`/editor/${detail.record_id}`);
        resolve();
      },
    );
    const offError = onEvent<{ error: string }>(
      "transcribe_error",
      (detail) => {
        offError();
        offComplete();
        offProgress();
        isImporting.value = false;
        store.showToast(detail.error ?? "Import transcription failed", "error");
        resolve();
      },
    );
  });
}

import { downloadAndTranscribe } from "../bridge";

async function handleDownloadAndTranscribe() {
  if (!downloadUrl.value) {
    store.showToast("请输入视频链接", "warning");
    return;
  }

  isDownloading.value = true;
  downloadProgress.value = 0;
  isImporting.value = true; // Reuse importing state for transcription phase
  importProgress.value = 0;

  // Listen for download progress
  const offDownloadProgress = onEvent<{ percent: number }>(
    "download_progress",
    ({ percent }) => {
      downloadProgress.value = percent;
    },
  );

  // Listen for transcription progress
  const offTranscribeProgress = onEvent<{ percent: number }>(
    "transcribe_progress",
    ({ percent }) => {
      importProgress.value = percent;
    },
  );

  const res = await downloadAndTranscribe(downloadUrl.value);
  if (!res.success) {
    isDownloading.value = false;
    isImporting.value = false;
    offDownloadProgress();
    offTranscribeProgress();
    store.showToast(res.error ?? "Failed to start download", "error");
    return;
  }

  // Wait for completion.
  await new Promise<void>((resolve) => {
    const offComplete = onEvent<{ record_id: string }>(
      "import_transcribe_complete",
      (detail) => {
        offComplete();
        offDownloadProgress();
        offTranscribeProgress();
        isDownloading.value = false;
        isImporting.value = false;
        router.push(`/editor/${detail.record_id}`);
        resolve();
      },
    );
    const offError = onEvent<{ error: string }>(
      "transcribe_error",
      (detail) => {
        offError();
        offComplete();
        offDownloadProgress();
        offTranscribeProgress();
        isDownloading.value = false;
        isImporting.value = false;
        store.showToast(detail.error ?? "Download/Transcription failed", "error");
        resolve();
      },
    );
  });
}

// ---- Fullscreen drag & drop (left/right split) ----
const SUPPORTED_AUDIO_EXT = [
  // Audio
  ".mp3", ".wav", ".m4a", ".m4b", ".m4p", ".aac", ".flac", ".ogg", ".oga",
  ".wma", ".opus", ".aiff", ".aif", ".ape", ".alac", ".amr", ".awb",
  ".mid", ".midi", ".wv", ".tak", ".tta", ".dsd", ".dff", ".dsf",
  // Video (ffmpeg can extract audio track)
  ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",
  ".3gp", ".ts", ".mts", ".m2ts", ".m4s", ".vob", ".ogv",
];
const fsDragCounter = ref(0);
const isDragOver = computed(() => fsDragCounter.value > 0);
const dropSide = ref<"left" | "right">("left");

function onWindowDragEnter(e: DragEvent) {
  e.preventDefault();
  fsDragCounter.value++;
}

function onWindowDragLeave(e: DragEvent) {
  e.preventDefault();
  fsDragCounter.value--;
}

function onWindowDragOver(e: DragEvent) {
  e.preventDefault();
  if (e.clientX < window.innerWidth / 2) {
    dropSide.value = "left";
  } else {
    dropSide.value = "right";
  }
}

function onWindowDrop(e: DragEvent) {
  e.preventDefault();
  const side = e.clientX < window.innerWidth / 2 ? "left" : "right";
  fsDragCounter.value = 0;

  setTimeout(async () => {
    const res = await call<string[]>("get_dropped_files");
    if (!res.success || !res.data || res.data.length === 0) return;

    const filePath = res.data[0];
    const ext = filePath.substring(filePath.lastIndexOf(".")).toLowerCase();
    if (!SUPPORTED_AUDIO_EXT.includes(ext)) {
      store.showToast(
        `不支持的文件格式: ${ext}，支持的格式: ${SUPPORTED_AUDIO_EXT.join(", ")}`,
        "error",
      );
      return;
    }

    if (side === "left") {
      handleFileSelected(filePath);
    } else {
      startImportTranscribe(filePath);
    }
  }, 150);
}

// Start listening for ASR events on mount.
onMounted(async () => {
  await Promise.all([loadModels(), loadAsrConfig()]);
  startListening();

  window.addEventListener("dragenter", onWindowDragEnter as EventListener);
  window.addEventListener("dragleave", onWindowDragLeave as EventListener);
  window.addEventListener("dragover", onWindowDragOver as EventListener);
  window.addEventListener("drop", onWindowDrop as EventListener);

  // Check for route query ?file=xxx (redirected from HomeView drag-drop).
  const fileQuery = route.query.file as string | undefined;
  if (fileQuery) {
    handleFileSelected(fileQuery);
  }
});

onUnmounted(() => {
  stopListening();
  resetState();
  window.removeEventListener("dragenter", onWindowDragEnter as EventListener);
  window.removeEventListener("dragleave", onWindowDragLeave as EventListener);
  window.removeEventListener("dragover", onWindowDragOver as EventListener);
  window.removeEventListener("drop", onWindowDrop as EventListener);
});
</script>

<template>
  <div
    class="mx-auto max-w-4xl px-4 py-6"
  >
    <!-- Header -->
    <div class="mb-4 flex items-center gap-3">
      <button class="btn btn-ghost btn-sm" @click="router.push('/')">
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
        返回
      </button>
      <h1 class="text-xl font-bold tracking-tight text-base-content">
        {{ isRecording ? "录音中..." : "新建录音" }}
      </h1>
    </div>

    <!-- Quick Settings Bar (hidden during active recording/transcription) -->
    <div
      v-if="!isRecording && !isTranscribingFile && !isLoadingModel && !isImporting"
      class="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-base-300 bg-base-200 p-3 text-sm"
    >
      <!-- ASR Engine -->
      <div class="flex items-center gap-1.5">
        <label class="text-base-content/50 whitespace-nowrap">引擎:</label>
        <select
          v-model="store.asrConfig.asr_backend"
          class="select select-bordered select-sm min-w-[130px]"
          @change="saveQuickSetting"
        >
          <option value="sherpa-onnx">sherpa-onnx</option>
          <option value="whisper-cpp">whisper.cpp</option>
        </select>
      </div>

      <!-- Streaming Model (hidden when whisper-cpp) -->
      <div v-if="store.asrConfig.asr_backend !== 'whisper-cpp'" class="flex items-center gap-1.5">
        <label class="text-base-content/50 whitespace-nowrap">流式模型:</label>
        <select
          v-model="store.asrConfig.active_streaming_model"
          class="select select-bordered select-sm min-w-[160px]"
          @change="saveQuickSetting"
        >
          <option value="">(自动)</option>
          <option
            v-for="m in installedStreamingModels"
            :key="m.model_id"
            :value="m.model_id"
          >{{ displayName(m.model_id) }}</option>
        </select>
      </div>

      <!-- Offline Model (hidden when whisper-cpp) -->
      <div v-if="store.asrConfig.asr_backend !== 'whisper-cpp'" class="flex items-center gap-1.5">
        <label class="text-base-content/50 whitespace-nowrap">离线模型:</label>
        <select
          v-model="store.asrConfig.active_offline_model"
          class="select select-bordered select-sm min-w-[160px]"
          @change="saveQuickSetting"
        >
          <option value="">(自动)</option>
          <option
            v-for="m in installedOfflineModels"
            :key="m.model_id"
            :value="m.model_id"
          >{{ displayName(m.model_id) }}</option>
        </select>
      </div>

      <!-- Whisper Model (shown when whisper-cpp) -->
      <div v-if="store.asrConfig.asr_backend === 'whisper-cpp'" class="flex items-center gap-1.5">
        <label class="text-base-content/50 whitespace-nowrap">Whisper模型:</label>
        <select
          v-model="store.asrConfig.active_whisper_model"
          class="select select-bordered select-sm min-w-[160px]"
          @change="saveQuickSetting"
        >
          <option value="">(自动)</option>
          <option
            v-for="m in installedWhisperModels"
            :key="m.model_id"
            :value="m.model_id"
          >{{ displayName(m.model_id) }}</option>
        </select>
      </div>

      <!-- Language -->
      <div class="flex items-center gap-1.5">
        <label class="text-base-content/50 whitespace-nowrap">语言:</label>
        <select
          v-model="store.asrConfig.language"
          class="select select-bordered select-sm"
          @change="saveQuickSetting"
        >
          <option v-for="lang in languages" :key="lang.value" :value="lang.value">
            {{ lang.label }}
          </option>
        </select>
      </div>
    </div>

    <!-- Recording controls -->
    <AudioRecorder
      @recording-complete="handleRecordingComplete"
      @file-selected="handleFileSelected"
    />

    <!-- Import & Transcribe -->
    <div
      class="mt-4 rounded-lg border-2 border-dashed border-base-300"
    >
      <!-- Progress bar shown during import -->
      <div v-if="isImporting" class="p-4">
        <div class="mb-2 flex items-center justify-between text-sm">
          <span>导入并转写中...</span>
          <span>{{ importProgress }}%</span>
        </div>
        <progress class="progress progress-primary w-full" :value="importProgress" max="100"></progress>
      </div>

      <!-- Default idle state -->
      <div v-else class="flex flex-col gap-4 p-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2 text-sm text-base-content/70">
            <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <span>拖放音频文件到页面任意位置，或</span>
          </div>
          <button
            v-if="!isRecording && !isTranscribingFile && !isLoadingModel"
            class="btn btn-secondary btn-sm"
            @click="handleImportAndTranscribe"
          >
            导入并转写
          </button>
        </div>

        <div class="flex items-center gap-2">
          <div class="flex-1">
            <input
              v-model="downloadUrl"
              type="text"
              placeholder="输入视频链接 (Bilibili, YouTube 等)"
              class="input input-bordered input-sm w-full"
              :disabled="isRecording || isTranscribingFile || isLoadingModel || isDownloading"
            />
          </div>
          <button
            v-if="!isRecording && !isTranscribingFile && !isLoadingModel"
            class="btn btn-primary btn-sm"
            :disabled="isDownloading || !downloadUrl"
            @click="handleDownloadAndTranscribe"
          >
            <span v-if="!isDownloading">下载转写</span>
            <span v-else class="loading loading-spinner"></span>
          </button>
        </div>

        <div v-if="isDownloading" class="flex items-center gap-3 text-sm">
          <span class="text-base-content/60">下载中...</span>
          <progress class="progress progress-primary flex-1" :value="downloadProgress" max="100"></progress>
          <span>{{ downloadProgress }}%</span>
        </div>
      </div>
    </div>

    <!-- Placeholder when idle -->
    <div
      v-if="finalSegments.length === 0 && !partialText && !isRecording && !isTranscribingFile && !isImporting"
      class="mt-6 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-base-300 py-20 text-base-content/40"
    >
      <svg class="mb-3 h-12 w-12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
        <path d="M19 10v2a7 7 0 01-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="23" />
        <line x1="8" y1="23" x2="16" y2="23" />
      </svg>
      <p class="mb-1 text-lg font-medium">准备录音</p>
      <p class="text-sm">点击"开始录音"或上传音频文件开始。</p>
    </div>

    <!-- Live transcript output -->
    <TranscriptPanel
      v-if="finalSegments.length > 0 || partialText"
      :segments="finalSegments"
      :partial-text="partialText"
      class="mt-6"
    />
  </div>

  <!-- Fullscreen drag overlay (left: direct transcribe, right: import & transcribe) -->
  <Teleport to="body">
    <div
      v-if="isDragOver"
      class="pointer-events-none fixed inset-0 z-50 flex"
    >
      <!-- Left half: direct transcribe -->
      <div
        class="flex flex-1 items-center justify-center transition-colors duration-150"
        :class="dropSide === 'left'
          ? 'bg-primary/10 border-r-2 border-primary border-dashed'
          : 'bg-primary/5'"
      >
        <div class="rounded-xl border-2 border-dashed px-12 py-8 text-center"
          :class="dropSide === 'left'
            ? 'border-primary bg-base-100/90'
            : 'border-primary/30 bg-base-100/50'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="mx-auto h-10 w-10 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
            <path d="M19 10v2a7 7 0 01-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
          <p class="text-lg font-semibold">直接转写</p>
          <p class="text-sm opacity-60">拖放到此处直接转录音频</p>
        </div>
      </div>
      <!-- Right half: import & transcribe -->
      <div
        class="flex flex-1 items-center justify-center transition-colors duration-150"
        :class="dropSide === 'right'
          ? 'bg-secondary/10 border-l-2 border-secondary border-dashed'
          : 'bg-secondary/5'"
      >
        <div class="rounded-xl border-2 border-dashed px-12 py-8 text-center"
          :class="dropSide === 'right'
            ? 'border-secondary bg-base-100/90'
            : 'border-secondary/30 bg-base-100/50'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="mx-auto h-10 w-10 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <p class="text-lg font-semibold">导入并转写</p>
          <p class="text-sm opacity-60">拖放到此处导入并转录音频</p>
        </div>
      </div>
    </div>
  </Teleport>
</template>
