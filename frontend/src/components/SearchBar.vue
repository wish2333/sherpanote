<script setup lang="ts">
/**
 * SearchBar - Search input with category filter dropdown.
 *
 * Emits debounced search events (300ms) and category changes.
 */
import { ref, watch } from "vue";
import type { RecordFilter } from "../types";

const props = withDefaults(
  defineProps<{
    categories?: string[];
    initialKeyword?: string;
    initialCategory?: string;
  }>(),
  {
    categories: () => [],
    initialKeyword: "",
    initialCategory: "",
  },
);

const emit = defineEmits<{
  search: [filter: RecordFilter];
}>();

const keyword = ref(props.initialKeyword);
const category = ref(props.initialCategory);

let searchTimer: ReturnType<typeof setTimeout>;

function emitSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    const filter: RecordFilter = {};
    if (keyword.value.trim()) {
      filter.keyword = keyword.value.trim();
    }
    if (category.value) {
      filter.category = category.value;
    }
    emit("search", filter);
  }, 300);
}

watch(keyword, emitSearch);

function onCategoryChange() {
  emitSearch();
}
</script>

<template>
  <div class="mb-4 flex gap-2">
    <input
      v-model="keyword"
      type="text"
      placeholder="搜索记录..."
      class="input input-bordered input-sm flex-1"
      @input="emitSearch"
    />
    <select
      v-model="category"
      class="select select-bordered select-sm w-32"
      @change="onCategoryChange"
    >
      <option value="">全部</option>
      <option v-for="cat in categories" :key="cat" :value="cat">
        {{ cat }}
      </option>
    </select>
  </div>
</template>
