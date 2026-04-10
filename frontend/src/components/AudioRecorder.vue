<script setup lang="ts">
/**
 * AudioRecorder - Recording control panel.
 *
 * Start/stop buttons, recording indicator, timer, and file upload.
 * Uses useRecording composable for audio capture logic.
 * File picker uses pywebview's native dialog (not HTML input)
 * to get the real OS file path.
 */
import { useRecording } from "../composables/useRecording";
import { useTranscript } from "../composables/useTranscript";
import { call } from "../bridge";
import { useAppStore } from "../stores/appStore";

const emit = defineEmits<{
  recordingComplete: [data: { text: string; segments: { text: string; timestamp: number[] }[]; duration: number; audio_path: string | null }];
  fileSelected: [filePath: string];
}>();

const {
  isRecording,
  isLoadingModel,
  elapsedTime,
  isSupported,
  silenceWarning,
  startRecording,
  stopRecording,
  formatTime,
} = useRecording();

const {
  isTranscribingFile,
  transcribeProgress,
} = useTranscript();

async function toggleRecording() {
  if (isRecording.value) {
    const result = await stopRecording();
    if (result && (result.text.trim().length > 0 || result.segments.length > 0)) {
      emit("recordingComplete", {
        text: result.text,
        segments: result.segments,
        duration: elapsedTime.value,
        audio_path: result.audio_path,
      });
    } else if (result) {
      // Recording completed but no speech was detected.
      useAppStore().showToast("No speech detected in this recording", "warning");
    }
  } else {
    await startRecording();
  }
}

async function pickAudioFile() {
  const res = await call<string[]>("pick_audio_file");
  if (res.success && res.data && res.data.length > 0) {
    emit("fileSelected", res.data[0]);
  }
}
</script>

<template>
  <div class="space-y-4">
    <!-- Model loading indicator -->
    <div v-if="isLoadingModel" class="flex items-center gap-4 rounded-lg border border-base-300 bg-base-200 p-4">
      <span class="loading loading-spinner loading-sm text-primary"></span>
      <span class="text-sm text-base-content/60">正在加载 ASR 模型...</span>
    </div>

    <!-- Recording status -->
    <div v-if="isRecording" class="flex items-center gap-4 rounded-lg border border-base-300 bg-base-200 p-4">
      <span class="loading loading-ball loading-sm text-error"></span>
      <span class="font-mono text-lg font-semibold text-base-content">
        {{ formatTime(elapsedTime) }}
      </span>
      <span class="text-sm text-base-content/60">录音中...</span>
    </div>

    <!-- Silence warning -->
    <div
      v-if="silenceWarning && isRecording"
      class="alert alert-warning text-sm"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
      <span>未检测到音频输入已超过 3 秒，请检查麦克风权限和输入设备。</span>
    </div>

    <!-- File transcription progress -->
    <div v-if="isTranscribingFile" class="rounded-lg border border-base-300 bg-base-200 p-4">
      <div class="mb-2 flex items-center justify-between text-sm">
        <span>转写文件中...</span>
        <span>{{ transcribeProgress }}%</span>
      </div>
      <progress class="progress progress-primary w-full" :value="transcribeProgress" max="100"></progress>
    </div>

    <!-- Control buttons -->
    <div class="flex gap-3">
      <button
        v-if="!isRecording && !isTranscribingFile && !isLoadingModel"
        class="btn btn-primary"
        :disabled="!isSupported"
        @click="toggleRecording"
      >
        <svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
          <circle cx="12" cy="12" r="6" />
        </svg>
        开始录音
      </button>

      <button
        v-if="isRecording"
        class="btn btn-error"
        @click="toggleRecording"
      >
        <svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
          <rect x="6" y="6" width="12" height="12" rx="2" />
        </svg>
        停止并保存
      </button>

      <button
        v-if="!isRecording && !isTranscribingFile && !isLoadingModel"
        class="btn btn-outline"
        @click="pickAudioFile"
      >
        <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        上传音频文件
      </button>
    </div>

    <!-- Unsupported warning -->
    <div v-if="!isSupported" class="alert alert-warning text-sm">
      当前环境不支持 Web Audio API。
    </div>
  </div>
</template>
