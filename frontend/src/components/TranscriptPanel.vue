<script setup lang="ts">
/**
 * TranscriptPanel - Live transcript display panel.
 *
 * Shows finalized segments in normal text and the current
 * partial result in gray italic. Auto-scrolls to bottom.
 */
import { ref, watch, nextTick } from "vue";

interface Segment {
  text: string;
  timestamp: number[];
}

const props = withDefaults(
  defineProps<{
    segments: Segment[];
    partialText: string;
    showTimestamps?: boolean;
  }>(),
  {
    showTimestamps: true,
  },
);

const panelRef = ref<HTMLElement | null>(null);

/** Auto-scroll to bottom when new content arrives. */
watch(
  () => [props.segments.length, props.partialText],
  async () => {
    await nextTick();
    if (panelRef.value) {
      panelRef.value.scrollTop = panelRef.value.scrollHeight;
    }
  },
);

function formatTimestamp(timestamp: number[]): string {
  if (!timestamp || timestamp.length < 2) return "";
  const start = timestamp[0];
  const m = Math.floor(start / 60);
  const s = Math.floor(start % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}
</script>

<template>
  <div
    ref="panelRef"
    class="rounded-lg border border-base-300 bg-base-100 p-4 max-h-[60vh] overflow-y-auto"
  >
    <h2 class="mb-3 text-sm font-semibold text-base-content/60">实时转写</h2>
    <div class="space-y-1 text-base leading-relaxed text-base-content">
      <p
        v-for="(seg, i) in segments"
        :key="i"
      >
        <span v-if="showTimestamps && seg.timestamp?.length" class="text-xs text-base-content/40 mr-2">
          {{ formatTimestamp(seg.timestamp) }}
        </span>
        {{ seg.text }}
      </p>
      <p v-if="partialText" class="italic text-base-content/50">
        {{ partialText }}
      </p>
    </div>
  </div>
</template>
