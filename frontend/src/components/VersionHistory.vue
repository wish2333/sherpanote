<script setup lang="ts">
/**
 * VersionHistory - Version history sidebar/drawer.
 *
 * Lists all versions for a record, highlights the current version,
 * and provides restore and delete actions per version.
 * Uses useStorage composable for version API calls.
 */
import { ref, onMounted, computed } from "vue";
import { useStorage } from "../composables/useStorage";
import { useAppStore } from "../stores/appStore";
import type { Version, TranscriptRecord } from "../types";

const props = defineProps<{
  recordId: string;
  currentVersion: number;
}>();

const emit = defineEmits<{
  restored: [record: TranscriptRecord];
  deleted: [];
}>();

const store = useAppStore();
const { getVersions, restoreVersion, deleteVersion } = useStorage();

const versions = ref<Version[]>([]);
const isLoading = ref(false);
const confirmRestoreVersion = ref<number | null>(null);
const isRestoring = ref(false);

const sortedVersions = computed(() =>
  [...versions.value].sort((a, b) => b.version - a.version),
);

async function loadVersions() {
  isLoading.value = true;
  versions.value = await getVersions(props.recordId);
  isLoading.value = false;
}

async function handleRestore(version: number) {
  confirmRestoreVersion.value = version;
}

async function confirmRestore() {
  if (confirmRestoreVersion.value === null) return;
  isRestoring.value = true;
  const restored = await restoreVersion(props.recordId, confirmRestoreVersion.value);
  if (restored) {
    store.showToast(`Restored to version ${confirmRestoreVersion.value}`, "success");
    emit("restored", restored);
  }
  isRestoring.value = false;
  confirmRestoreVersion.value = null;
}

async function handleDelete(version: number) {
  const success = await deleteVersion(props.recordId, version);
  if (success) {
    store.showToast(`Version v${version} deleted`, "info");
    await loadVersions();
    emit("deleted");
  }
}

function cancelRestore() {
  confirmRestoreVersion.value = null;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

onMounted(loadVersions);
</script>

<template>
  <div class="rounded-lg border border-base-300 bg-base-100 p-4">
    <h2 class="mb-3 text-sm font-semibold text-base-content/60">Version History</h2>

    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-4">
      <span class="loading loading-spinner loading-sm text-primary"></span>
    </div>

    <!-- Empty -->
    <p v-else-if="sortedVersions.length === 0" class="text-sm text-base-content/40">
      No version history yet. Click "Save Version" to create a snapshot.
    </p>

    <!-- Version list -->
    <div v-else class="space-y-1 max-h-[50vh] overflow-y-auto">
      <div
        v-for="ver in sortedVersions"
        :key="ver.version"
        class="flex items-start justify-between rounded px-2 py-1.5 text-sm"
        :class="ver.version === currentVersion ? 'bg-primary/10 border border-primary/30' : 'hover:bg-base-200'"
      >
        <div class="min-w-0 flex-1">
          <span class="font-medium">
            v{{ ver.version }}
          </span>
          <span v-if="ver.version === currentVersion" class="badge badge-primary badge-xs ml-1">
            current
          </span>
          <div class="text-xs text-base-content/40">
            {{ formatDate(ver.created_at) }}
          </div>
          <!-- Text preview for quick comparison -->
          <div class="mt-1 text-xs text-base-content/30 truncate max-w-[200px]" :title="ver.transcript">
            {{ ver.transcript ? ver.transcript.slice(0, 80) : '(empty)' }}{{ ver.transcript && ver.transcript.length > 80 ? '...' : '' }}
          </div>
        </div>
        <div class="flex items-center gap-1 shrink-0 ml-2">
          <button
            v-if="ver.version !== currentVersion"
            class="btn btn-ghost btn-xs"
            :disabled="isRestoring"
            @click="handleRestore(ver.version)"
          >
            Restore
          </button>
          <button
            class="btn btn-ghost btn-xs text-error"
            title="Delete this version"
            @click="handleDelete(ver.version)"
          >
            <svg class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
              <path d="M10 11v6" />
              <path d="M14 11v6" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Restore confirmation modal -->
    <dialog
      v-if="confirmRestoreVersion !== null"
      class="modal modal-open"
    >
      <div class="modal-box">
        <h3 class="text-lg font-bold">Confirm Restore</h3>
        <p class="py-4 text-sm">
          Restore this record to version <strong>{{ confirmRestoreVersion }}</strong>?
          This will create a new version with the restored content.
        </p>
        <div class="modal-action">
          <button
            class="btn btn-ghost btn-sm"
            :disabled="isRestoring"
            @click="cancelRestore"
          >
            Cancel
          </button>
          <button
            class="btn btn-primary btn-sm"
            :disabled="isRestoring"
            @click="confirmRestore"
          >
            <span v-if="isRestoring" class="loading loading-spinner loading-xs"></span>
            Restore
          </button>
        </div>
      </div>
      <form method="dialog" class="modal-backdrop" @click="cancelRestore">
        <button>close</button>
      </form>
    </dialog>
  </div>
</template>
