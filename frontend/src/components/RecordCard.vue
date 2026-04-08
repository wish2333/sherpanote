<script setup lang="ts">
/**
 * RecordCard - Single transcript record card.
 *
 * Displays title, duration, creation date, category badge,
 * AI status badge, and a delete button.
 */
import type { TranscriptRecord } from "../types";

defineProps<{
  record: TranscriptRecord;
}>();

const emit = defineEmits<{
  click: [];
  delete: [];
  recognize: [];
}>();

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("zh-CN", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function hasAiResults(record: TranscriptRecord): boolean {
  return record.ai_results && Object.keys(record.ai_results).length > 0;
}
</script>

<template>
  <div
    class="card bg-base-100 border border-base-300 shadow-md cursor-pointer hover:shadow-xl transition-shadow"
    @click="emit('click')"
  >
    <div class="card-body p-4">
      <div class="flex items-center justify-between">
        <div class="min-w-0 flex-1">
          <h3 class="card-title text-base truncate">
            {{ record.title || "Untitled" }}
          </h3>
          <div class="mt-1 flex items-center gap-3 text-sm text-base-content/60">
            <span v-if="record.duration_seconds > 0">
              {{ formatDuration(record.duration_seconds) }}
            </span>
            <span>{{ formatDate(record.created_at) }}</span>
            <span v-if="record.category" class="badge badge-ghost badge-sm">
              {{ record.category }}
            </span>
            <span
              v-for="tag in record.tags?.slice(0, 3)"
              :key="tag"
              class="badge badge-outline badge-sm"
            >
              {{ tag }}
            </span>
            <span
              v-if="record.tags && record.tags.length > 3"
              class="badge badge-ghost badge-sm"
            >
              +{{ record.tags.length - 3 }}
            </span>
          </div>
        </div>
        <div class="flex items-center gap-1" @click.stop>
          <span
            v-if="hasAiResults(record)"
            class="badge badge-info badge-sm"
          >
            AI
          </span>
          <button
            v-if="record.audio_path"
            class="btn btn-ghost btn-xs"
            title="Re-recognize audio"
            @click="emit('recognize')"
          >
            <svg class="h-4 w-4 text-base-content/40 hover:text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
              <path d="M19 10v2a7 7 0 01-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          </button>
          <button
            class="btn btn-ghost btn-xs"
            title="Delete"
            @click="emit('delete')"
          >
            <svg class="h-4 w-4 text-base-content/40 hover:text-error" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
              <path d="M10 11v6" />
              <path d="M14 11v6" />
              <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" />
            </svg>
          </button>
          <svg class="h-4 w-4 text-base-content/30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 18l6-6-6-6" />
          </svg>
        </div>
      </div>
    </div>
  </div>
</template>
