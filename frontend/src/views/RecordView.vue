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
import { onMounted, onUnmounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useRecording } from "../composables/useRecording";
import { useTranscript } from "../composables/useTranscript";
import { useDragDrop } from "../composables/useDragDrop";
import AudioRecorder from "../components/AudioRecorder.vue";
import TranscriptPanel from "../components/TranscriptPanel.vue";

const router = useRouter();
const route = useRoute();

const {
  isRecording,
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

// File drag-and-drop in this view (counter-based to prevent flicker).
const {
  isDraggingOver: isDraggingFile,
  onDragEnter,
  onDragLeave,
  onDragOver,
  onDrop,
} = useDragDrop((filePath) => {
  handleFileSelected(filePath);
});

// Start listening for ASR events on mount.
onMounted(() => {
  startListening();

  // Check for route query ?file=xxx (redirected from HomeView drag-drop).
  const fileQuery = route.query.file as string | undefined;
  if (fileQuery) {
    handleFileSelected(fileQuery);
  }
});

onUnmounted(() => {
  stopListening();
  resetState();
});
</script>

<template>
  <div
    class="mx-auto max-w-4xl px-4 py-6"
    @dragenter="onDragEnter"
    @dragleave="onDragLeave"
    @dragover="onDragOver"
    @drop="onDrop"
  >
    <!-- Header -->
    <div class="mb-6 flex items-center gap-3">
      <button class="btn btn-ghost btn-sm" @click="router.push('/')">
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
        Back
      </button>
      <h1 class="text-xl font-bold tracking-tight text-base-content">
        {{ isRecording ? "Recording..." : "New Recording" }}
      </h1>
    </div>

    <!-- Drag overlay -->
    <div
      v-if="isDraggingFile"
      class="mb-4 rounded-lg border-2 border-dashed border-primary bg-primary/5 p-6 text-center"
    >
      <p class="text-primary font-medium">Drop audio file to transcribe</p>
    </div>

    <!-- Recording controls -->
    <AudioRecorder
      @recording-complete="handleRecordingComplete"
      @file-selected="handleFileSelected"
    />

    <!-- Live transcript output -->
    <TranscriptPanel
      v-if="finalSegments.length > 0 || partialText"
      :segments="finalSegments"
      :partial-text="partialText"
      class="mt-6"
    />

    <!-- Placeholder when idle -->
    <div
      v-if="finalSegments.length === 0 && !partialText && !isRecording && !isTranscribingFile"
      class="mt-6 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-base-300 py-20 text-base-content/40"
    >
      <svg class="mb-3 h-12 w-12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
        <path d="M19 10v2a7 7 0 01-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="23" />
        <line x1="8" y1="23" x2="16" y2="23" />
      </svg>
      <p class="mb-1 text-lg font-medium">Ready to Record</p>
      <p class="text-sm">Click "Start Recording" or upload an audio file to begin.</p>
    </div>
  </div>
</template>
