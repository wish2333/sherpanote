<script setup lang="ts">
/**
 * App.vue - Root layout with navbar, transcription progress bar, and toast notifications.
 *
 * Uses ThemeToggle component and renders toast container.
 */
import { onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { onEvent } from "./bridge";
import { useAppStore } from "./stores/appStore";
import { waitForPyWebView } from "./bridge";
import ThemeToggle from "./components/ThemeToggle.vue";

const store = useAppStore();
const router = useRouter();

// Global transcription progress tracking.
const cleanupFns: (() => void)[] = [];

onMounted(async () => {
  store.applyTheme();

  try {
    await waitForPyWebView();
    store.ready = true;
  } catch {
    store.ready = false;
  }

  // Listen for global transcription events so progress bar
  // is visible even when user navigates away from the transcribing page.
  const offProgress = onEvent<{ percent: number }>(
    "transcribe_progress",
    ({ percent }) => {
      store.transcribeProgress = percent;
      store.isTranscribing = true;
    },
  );
  const offComplete = onEvent("transcribe_complete", () => {
    store.isTranscribing = false;
    store.transcribeProgress = 0;
  });
  const offRetranscribe = onEvent("retranscribe_complete", () => {
    store.isTranscribing = false;
    store.transcribeProgress = 0;
  });
  const offImport = onEvent("import_transcribe_complete", () => {
    store.isTranscribing = false;
    store.transcribeProgress = 0;
  });
  const offError = onEvent("transcribe_error", () => {
    store.isTranscribing = false;
    store.transcribeProgress = 0;
  });

  cleanupFns.push(offProgress, offComplete, offRetranscribe, offImport, offError);
});

onBeforeUnmount(() => {
  cleanupFns.forEach((fn) => fn());
  cleanupFns.length = 0;
});
</script>

<template>
  <!-- Top navigation bar -->
  <div class="navbar bg-base-100 border-b border-base-300 px-4">
    <!-- Left: logo + navigation -->
    <div class="navbar-start gap-2">
      <a class="text-xl font-bold tracking-tight text-base-content" @click="router.push('/')">
        SherpaNote
      </a>
      <ul class="menu menu-horizontal gap-1">
        <li>
          <a
            :class="{ 'bg-base-200': $route.path === '/' }"
            @click="router.push('/')"
          >
            <span class="text-sm">转录记录</span>
          </a>
        </li>
        <li>
          <a
            :class="{ 'bg-base-200': $route.path === '/record' }"
            @click="router.push('/record')"
          >
            <span class="text-sm">录音/转录</span>
          </a>
        </li>
        <li>
          <a
            :class="{ 'bg-base-200': $route.path === '/audio' }"
            @click="router.push('/audio')"
          >
            <span class="text-sm">音频管理器</span>
          </a>
        </li>
        <li>
          <a
            :class="{ 'bg-base-200': $route.path === '/ocr' }"
            @click="router.push('/ocr')"
          >
            <span class="text-sm">OCR</span>
          </a>
        </li>
      </ul>
    </div>

    <!-- Right: status + actions -->
    <div class="navbar-end gap-2">
      <!-- Transcription progress indicator -->
      <div v-if="store.isTranscribing" class="flex items-center gap-2">
        <span class="loading loading-spinner loading-xs text-primary"></span>
        <span class="text-xs text-base-content/60">{{ store.transcribeProgress }}%</span>
      </div>

      <!-- Bridge status indicator -->
      <span
        class="badge badge-sm"
        :class="store.ready ? 'badge-success' : 'badge-warning'"
      >
        {{ store.ready ? "Connected" : "Connecting..." }}
      </span>

      <!-- Theme toggle -->
      <ThemeToggle />

      <!-- Settings -->
      <button class="btn btn-ghost btn-sm btn-circle" @click="router.push('/settings')">
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12.22 2h-.44a2 2 0 00-2 2v.18a2 2 0 01-1 1.73l-.43.25a2 2 0 01-2 0l-.15-.08a2 2 0 00-2.73.73l-.22.38a2 2 0 00.73 2.73l.15.1a2 2 0 011 1.72v.51a2 2 0 01-1 1.74l-.15.09a2 2 0 00-.73 2.73l.22.38a2 2 0 002.73.73l.15-.08a2 2 0 012 0l.43.25a2 2 0 011 1.73V20a2 2 0 002 2h.44a2 2 0 002-2v-.18a2 2 0 011-1.73l.43-.25a2 2 0 012 0l.15.08a2 2 0 002.73-.73l.22-.39a2 2 0 00-.73-2.73l-.15-.08a2 2 0 01-1-1.74v-.5a2 2 0 011-1.74l.15-.09a2 2 0 00.73-2.73l-.22-.38a2 2 0 00-2.73-.73l-.15.08a2 2 0 01-2 0l-.43-.25a2 2 0 01-1-1.73V4a2 2 0 00-2-2z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      </button>
    </div>
  </div>

  <!-- Global transcription progress bar -->
  <div v-if="store.isTranscribing" class="w-full bg-base-200">
    <div
      class="h-1 bg-primary transition-all duration-300 ease-out"
      :style="{ width: `${Math.min(store.transcribeProgress, 100)}%` }"
    ></div>
  </div>

  <!-- Page content -->
  <main class="min-h-[calc(100vh-56px)] bg-base-100">
    <router-view />
  </main>

  <!-- Toast notifications -->
  <div class="toast toast-top toast-end z-50">
    <div
      v-for="toast in store.toasts"
      :key="toast.id"
      class="alert max-w-sm shadow-lg"
      :class="{
        'alert-success': toast.type === 'success',
        'alert-error': toast.type === 'error',
        'alert-warning': toast.type === 'warning',
        'alert-info': toast.type === 'info',
      }"
    >
      <span class="text-sm">{{ toast.message }}</span>
    </div>
  </div>
</template>
