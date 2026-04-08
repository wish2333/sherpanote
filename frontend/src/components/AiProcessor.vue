<script setup lang="ts">
/**
 * AiProcessor - AI processing panel with mode selection and streaming output.
 *
 * Provides 4 AI modes (polish, note, mindmap, brainstorm),
 * streaming result display, saved results list, copy button,
 * and mind map preview for mindmap mode output.
 * Uses useAiProcess composable.
 */
import { ref, computed } from "vue";
import { useAiProcess } from "../composables/useAiProcess";
import MarkdownRenderer from "./MarkdownRenderer.vue";
import MindMapPreview from "./MindMapPreview.vue";
import type { TranscriptRecord, AiMode, AiResults } from "../types";

const props = defineProps<{
  record: TranscriptRecord | null;
  editorText: string;
}>();

const emit = defineEmits<{
  resultSaved: [record: TranscriptRecord];
}>();

const {
  isProcessing,
  currentMode,
  currentResult,
  showPanel,
  aiModes,
  processText,
  saveResult,
  copyResult,
  cancelProcessing,
} = useAiProcess();

/** Toggle between text and mind map view for mindmap mode. */
const showMindMap = ref(false);

/** Saved results from the record (excluding current mode if it's live). */
const savedResults = computed<AiResults>(() => {
  return props.record?.ai_results ?? {};
});

function getSavedModes(): AiMode[] {
  if (!savedResults.value) return [];
  return Object.keys(savedResults.value) as AiMode[];
}

const isMindMapMode = computed(() => currentMode.value === "mindmap");

async function handleProcess() {
  showMindMap.value = false;
  await processText(props.editorText, currentMode.value);
}

async function handleSave() {
  if (!props.record) return;
  const updated = await saveResult(props.record);
  if (updated) {
    emit("resultSaved", updated);
  }
}

function viewSavedResult(mode: AiMode) {
  const content = savedResults.value[mode];
  if (content) {
    currentMode.value = mode;
    currentResult.value = content;
    showPanel.value = true;
    showMindMap.value = mode === "mindmap";
  }
}
</script>

<template>
  <div class="space-y-4">
    <!-- AI mode selector -->
    <div class="rounded-lg border border-base-300 bg-base-100 p-4">
      <h2 class="mb-3 text-sm font-semibold text-base-content/60">AI Processing</h2>
      <div class="space-y-2">
        <button
          v-for="mode in aiModes"
          :key="mode.key"
          class="btn btn-sm w-full justify-start"
          :class="currentMode === mode.key ? 'btn-primary' : 'btn-ghost'"
          @click="currentMode = mode.key"
        >
          <span>{{ mode.label }}</span>
          <span class="text-xs opacity-60">{{ mode.desc }}</span>
        </button>
      </div>
      <button
        class="btn btn-primary btn-sm mt-3 w-full"
        :disabled="isProcessing || !editorText.trim()"
        @click="handleProcess"
      >
        <span v-if="isProcessing" class="loading loading-spinner loading-xs"></span>
        {{ isProcessing ? "Processing..." : "Process" }}
      </button>
      <button
        v-if="isProcessing"
        class="btn btn-error btn-outline btn-sm mt-1 w-full"
        @click="cancelProcessing"
      >
        Cancel
      </button>
    </div>

    <!-- AI result panel -->
    <div
      v-if="showPanel"
      class="rounded-lg border border-base-300 bg-base-100 p-4"
    >
      <div class="mb-2 flex items-center justify-between">
        <h2 class="text-sm font-semibold text-base-content/60">
          Result ({{ currentMode }})
        </h2>
        <div class="flex gap-1">
          <!-- Mind map toggle for mindmap mode -->
          <button
            v-if="isMindMapMode && currentResult"
            class="btn btn-ghost btn-xs"
            :class="showMindMap ? 'btn-active' : ''"
            @click="showMindMap = !showMindMap"
            title="Toggle mind map view"
          >
            Map
          </button>
          <button
            v-if="currentResult && !isProcessing"
            class="btn btn-ghost btn-xs"
            @click="handleSave"
          >
            Save
          </button>
          <button
            v-if="currentResult"
            class="btn btn-ghost btn-xs"
            @click="copyResult"
          >
            Copy
          </button>
        </div>
      </div>

      <!-- Mind map preview -->
      <MindMapPreview
        v-if="showMindMap && currentResult"
        :content="currentResult"
      />

      <!-- Markdown rendered output -->
      <MarkdownRenderer
        v-else-if="currentResult && !showMindMap"
        :content="currentResult"
      />
      <div v-else-if="isProcessing" class="flex justify-center py-4">
        <span class="loading loading-dots loading-md text-primary"></span>
      </div>
      <p v-else class="text-sm text-base-content/40">
        Click "Process" to start AI analysis.
      </p>
    </div>

    <!-- Saved AI results list -->
    <div
      v-if="getSavedModes().length > 0"
      class="rounded-lg border border-base-300 bg-base-100 p-4"
    >
      <h2 class="mb-3 text-sm font-semibold text-base-content/60">Saved AI Results</h2>
      <div class="space-y-2">
        <button
          v-for="mode in getSavedModes()"
          :key="mode"
          class="btn btn-ghost btn-sm w-full justify-start"
          @click="viewSavedResult(mode)"
        >
          {{ mode }}
          <span class="text-xs opacity-60 truncate max-w-[150px]">
            {{ String(savedResults[mode]).slice(0, 30) }}...
          </span>
        </button>
      </div>
    </div>
  </div>
</template>
