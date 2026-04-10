<script setup lang="ts">
/**
 * AiProcessor - Compact AI processing control panel.
 *
 * Layout:
 *   1. AI Provider dropdown (API preset switching)
 *   2. Mode buttons: built-in modes + custom presets, click to select
 *   3. Process / Cancel action buttons
 *   4. Saved results navigation list
 *
 * Emits: process, selectResult, deleteResult, cancel
 */
import { ref, computed, onMounted } from "vue";
import { call, onEvent } from "../bridge";
import { useAppStore } from "../stores/appStore";
import type { AiMode, AiResults, AiProcessingPreset, AiPreset } from "../types";

const props = defineProps<{
  record: { id: string; ai_results: AiResults } | null;
  editorText: string;
  activeResultMode: string | null;
}>();

const emit = defineEmits<{
  process: [mode: string, presetId: string | null, customPrompt: string | null];
  selectResult: [mode: string];
  deleteResult: [mode: string];
  cancel: [];
}>();

const store = useAppStore();

const isProcessing = ref(false);
const currentMode = ref<AiMode>("polish");
const truncationWarning = ref(false);

/** API presets for quick-switching. */
const apiPresets = ref<AiPreset[]>([]);
const activeApiPresetId = ref<string | null>(null);

/** Processing presets (prompt templates). */
const processingPresets = ref<AiProcessingPreset[]>([]);

const savedResults = computed<AiResults>(() => props.record?.ai_results ?? {});
const savedModes = computed<string[]>(() => Object.keys(savedResults.value));

/** Custom (non-builtin) processing presets shown as extra mode buttons. */
const customPresets = computed(() =>
  processingPresets.value.filter(p => !p.id.startsWith("builtin_")),
);

/** Resolve the custom prompt for the currently selected mode. */
function getCustomPrompt(): string | null {
  if (!currentMode.value.includes("_preset_")) return null;
  const presetId = currentMode.value.split("_preset_")[1];
  return processingPresets.value.find(p => p.id === presetId)?.prompt ?? null;
}

/** Resolve the processing preset ID from the current mode key. */
function getPresetId(): string | null {
  if (!currentMode.value.includes("_preset_")) return null;
  return currentMode.value.split("_preset_")[1];
}

function selectMode(mode: AiMode) {
  currentMode.value = mode;
}

async function loadApiPresets() {
  const res = await call<AiPreset[]>("list_ai_presets");
  if (res.success && res.data) {
    apiPresets.value = res.data;
    const active = res.data.find((p) => p.is_active);
    if (active) activeApiPresetId.value = active.id;
  }
}

async function loadProcessingPresets() {
  const res = await call<AiProcessingPreset[]>("list_processing_presets");
  if (res.success && res.data) {
    processingPresets.value = res.data;
  }
}

async function switchApiPreset(presetId: string) {
  const res = await call("set_active_ai_preset", presetId);
  if (res.success) {
    activeApiPresetId.value = presetId;
    store.showToast("Switched AI provider", "success");
  }
}

function handleProcess() {
  const mode = currentMode.value;
  const customPrompt = getCustomPrompt();
  const presetId = getPresetId();
  isProcessing.value = true;
  truncationWarning.value = false;
  emit("process", mode, presetId, customPrompt);

  const offComplete = onEvent<{ result: string; truncated: boolean }>("ai_complete", (detail) => {
    isProcessing.value = false;
    if (detail.truncated) {
      truncationWarning.value = true;
      store.showToast("Output may be truncated. Increase max_tokens in settings.", "warning");
    }
    offComplete();
  });

  const offError = onEvent<{ error: string }>("ai_error", (detail) => {
    isProcessing.value = false;
    store.showToast(detail.error, "error");
    offComplete();
    offError();
  });
}

function handleCancel() {
  emit("cancel");
  isProcessing.value = false;
}

function handleSelectResult(mode: string) {
  emit("selectResult", mode);
}

function handleDeleteResult(mode: string) {
  emit("deleteResult", mode);
}

function getResultLabel(mode: string): string {
  if (mode.includes("_preset_")) {
    // Key format: {presetName}_preset_{presetId}
    return mode.split("_preset_")[0];
  }
  return mode;
}

onMounted(() => {
  loadApiPresets();
  loadProcessingPresets();
});
</script>

<template>
  <div class="rounded-lg border border-base-300 bg-base-100 p-4 space-y-4">
    <!-- AI Provider -->
    <div>
      <h2 class="text-sm font-semibold text-base-content/50 uppercase tracking-wider mb-2">AI 服务商</h2>
      <select
        :value="activeApiPresetId"
        class="select select-bordered select-sm w-full"
        @change="switchApiPreset(($event.target as HTMLSelectElement).value)"
      >
        <option v-for="p in apiPresets" :key="p.id" :value="p.id">
          {{ p.name }} ({{ p.provider }}/{{ p.model }})
        </option>
      </select>
    </div>

    <!-- Processing Mode (buttons only) -->
    <div>
      <h2 class="text-sm font-semibold text-base-content/50 uppercase tracking-wider mb-2">处理模式</h2>
      <div class="space-y-1">
        <!-- Built-in modes -->
        <button
          v-for="m in [
            { key: 'polish' as AiMode, label: '润色', desc: '修饰文本' },
            { key: 'note' as AiMode, label: '笔记', desc: '结构化笔记' },
            { key: 'mindmap' as AiMode, label: '思维导图', desc: 'Markmap' },
            { key: 'brainstorm' as AiMode, label: '头脑风暴', desc: '发散思考' },
          ]"
          :key="m.key"
          class="btn btn-sm w-full justify-start"
          :class="currentMode === m.key ? 'btn-primary' : 'btn-ghost'"
          @click="selectMode(m.key)"
        >
          {{ m.label }}
          <span class="text-xs opacity-50 ml-auto">{{ m.desc }}</span>
        </button>

        <!-- Custom presets -->
        <template v-if="customPresets.length > 0">
          <div class="divider my-1 text-xs text-base-content/30">自定义</div>
          <button
            v-for="p in customPresets"
            :key="p.id"
            class="btn btn-sm w-full justify-start"
            :class="currentMode === `${p.name}_preset_${p.id}` ? 'btn-primary' : 'btn-ghost'"
            @click="selectMode(`${p.name}_preset_${p.id}` as AiMode)"
          >
            {{ p.name }}
          </button>
        </template>
      </div>
    </div>

    <!-- Process / Cancel -->
    <div class="space-y-1">
      <button
        class="btn btn-primary w-full"
        :disabled="isProcessing || !editorText.trim()"
        @click="handleProcess"
      >
        <span v-if="isProcessing" class="loading loading-spinner loading-sm"></span>
        {{ isProcessing ? "处理中..." : "处理" }}
      </button>
      <button
        v-if="isProcessing"
        class="btn btn-error btn-outline w-full"
        @click="handleCancel"
      >取消</button>
    </div>

    <!-- Saved results navigation -->
    <div v-if="savedModes.length > 0">
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-semibold text-base-content/50 uppercase tracking-wider">
          结果 ({{ savedModes.length }})
        </h3>
      </div>
      <div class="space-y-1 max-h-[35vh] overflow-y-auto">
        <div
          v-for="mode in savedModes"
          :key="mode"
          class="flex items-center rounded border px-3 py-2 transition-colors"
          :class="activeResultMode === mode
            ? 'border-primary bg-primary/10 text-primary'
            : 'border-transparent hover:bg-base-200 text-base-content'"
        >
          <button
            class="flex-1 min-w-0 text-left"
            @click="handleSelectResult(mode)"
          >
            <span class="capitalize font-medium">{{ getResultLabel(mode) }}</span>
            <span class="text-xs opacity-40 block truncate">
              {{ String(savedResults[mode]).slice(0, 60) }}
            </span>
          </button>
          <button
            class="btn btn-ghost btn-xs text-error flex-shrink-0 ml-1"
            title="删除"
            @click="handleDeleteResult(mode)"
          >
            <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
