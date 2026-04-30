<script setup lang="ts">
/**
 * File drop input component.
 *
 * Drag-and-drop zone or click to open file dialog.
 * Shows filename with clear button, hover for full path.
 * File type validation is performed on the frontend.
 *
 * Phase 3.5.1: Add fullscreenDrop prop for document-level drag handling.
 * Phase 5: Add multiple prop for single-file constraint mode.
 */
import { ref, computed, onMounted, onUnmounted } from "vue"
import { useI18n } from "vue-i18n"
import { call } from "../../bridge"
import { logError } from "../../utils/logger"

const { t } = useI18n()

const props = withDefaults(defineProps<{
  modelValue: string
  accept?: string
  placeholder?: string
  fullscreenDrop?: boolean
  multiple?: boolean
  disabled?: boolean
}>(), {
  fullscreenDrop: false,
  multiple: true,
  disabled: false,
})

const emit = defineEmits<{
  "update:modelValue": [value: string]
}>()

const isDragging = ref(false)
const isFullscreenDragging = ref(false)
const error = ref("")
let dragCounter = 0

const acceptedExts = computed(() => {
  if (!props.accept) return null
  return new Set(
    props.accept
      .split(",")
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean),
  )
})

const fileName = computed(() => {
  if (!props.modelValue) return ""
  return props.modelValue.split(/[/\\]/).pop() ?? props.modelValue
})

function validateExtension(path: string): boolean {
  const exts = acceptedExts.value
  if (!exts || exts.size === 0) return true
  const dotIdx = path.lastIndexOf(".")
  if (dotIdx === -1) return false
  const ext = path.slice(dotIdx).toLowerCase()
  return exts.has(ext)
}

function onDragEnter(e: DragEvent): void {
  if (props.disabled) return
  e.preventDefault()
  dragCounter++
  if (dragCounter === 1) isDragging.value = true
}

function onDragOver(e: DragEvent): void {
  if (props.disabled) return
  e.preventDefault()
}

function onDragLeave(e: DragEvent): void {
  if (props.disabled) return
  e.preventDefault()
  dragCounter--
  if (dragCounter === 0) isDragging.value = false
}

async function onDrop(e: DragEvent): Promise<void> {
  e.preventDefault()
  isDragging.value = false
  dragCounter = 0
  error.value = ""
  // Wait for pywebvue's document-level _on_drop to process
  await new Promise((resolve) => setTimeout(resolve, 80))
  const res = await call<string[]>("get_dropped_files")
  if (res.success && res.data && res.data.length > 0) {
    if (!props.multiple && res.data.length > 1) {
      error.value = t("common.onlyOneFile")
      return
    }
    const paths = props.multiple ? res.data : [res.data[0]]
    for (const path of paths) {
      if (validateExtension(path)) {
        emit("update:modelValue", path)
      } else {
        error.value = t("common.unsupportedFileType", { accept: props.accept })
        break
      }
    }
  }
}

// Fullscreen drag handlers
let fsDragCounter = 0

function onFullscreenDragEnter(e: DragEvent): void {
  e.preventDefault()
  fsDragCounter++
  if (fsDragCounter === 1) isFullscreenDragging.value = true
}

function onFullscreenDragOver(e: DragEvent): void {
  e.preventDefault()
}

function onFullscreenDragLeave(e: DragEvent): void {
  e.preventDefault()
  fsDragCounter--
  if (fsDragCounter === 0) isFullscreenDragging.value = false
}

async function onFullscreenDrop(e: DragEvent): Promise<void> {
  e.preventDefault()
  isFullscreenDragging.value = false
  fsDragCounter = 0
  error.value = ""
  await new Promise((resolve) => setTimeout(resolve, 80))
  const res = await call<string[]>("get_dropped_files")
  if (res.success && res.data && res.data.length > 0) {
    if (!props.multiple && res.data.length > 1) {
      error.value = t("common.onlyOneFile")
      return
    }
    const paths = props.multiple ? res.data : [res.data[0]]
    for (const path of paths) {
      if (validateExtension(path)) {
        emit("update:modelValue", path)
      } else {
        error.value = t("common.unsupportedFileType", { accept: props.accept })
        break
      }
    }
  }
}

async function openFileDialog(): Promise<void> {
  if (props.disabled) return
  error.value = ""
  try {
    if (props.multiple) {
      const res = await call<string[]>("select_files")
      if (res.success && res.data && res.data.length > 0) {
        for (const path of res.data) {
          if (validateExtension(path)) {
            emit("update:modelValue", path)
          } else {
            error.value = t("common.unsupportedFileType", { accept: props.accept })
            return
          }
        }
      }
    } else {
      const res = await call<string>("select_file_filtered")
      if (res.success && res.data) {
        if (validateExtension(res.data)) {
          emit("update:modelValue", res.data)
        } else {
          error.value = t("common.unsupportedFileType", { accept: props.accept })
        }
      }
    }
  } catch (err) {
    logError("FileDropInput", "file dialog failed", err)
    error.value = t("common.fileDialogFailed")
  }
}

function clear(): void {
  emit("update:modelValue", "")
  error.value = ""
}

onMounted(() => {
  if (props.fullscreenDrop) {
    document.addEventListener("dragenter", onFullscreenDragEnter)
    document.addEventListener("dragover", onFullscreenDragOver)
    document.addEventListener("dragleave", onFullscreenDragLeave)
    document.addEventListener("drop", onFullscreenDrop)
  }
})

onUnmounted(() => {
  dragCounter = 0
  if (props.fullscreenDrop) {
    document.removeEventListener("dragenter", onFullscreenDragEnter)
    document.removeEventListener("dragover", onFullscreenDragOver)
    document.removeEventListener("dragleave", onFullscreenDragLeave)
    document.removeEventListener("drop", onFullscreenDrop)
  }
})
</script>

<template>
  <div
    class="relative"
    @dragenter="onDragEnter"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <!-- Fullscreen drag overlay -->
    <div
      v-if="isFullscreenDragging"
      class="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-primary/10"
    >
      <div class="rounded-xl border-2 border-dashed border-primary bg-base-100/80 px-12 py-8 text-center">
        <svg xmlns="http://www.w3.org/2000/svg" class="mx-auto h-10 w-10 text-primary mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        <p class="text-lg font-semibold text-primary">{{ t("common.dropFileHere") }}</p>
      </div>
    </div>

    <!-- Drop zone / display -->
    <div
      class="flex items-center gap-2 rounded-lg border border-dashed px-3 py-2 text-sm transition-colors"
      :class="[
        disabled ? 'opacity-50 cursor-not-allowed border-base-300 bg-base-200' : 'cursor-pointer',
        !disabled && error
        ? 'border-error bg-error/10'
        : (modelValue
          ? (isDragging ? 'border-primary bg-primary/10' : 'border-base-300 hover:border-base-content/30')
          : (isDragging ? 'border-primary bg-primary/10' : 'border-base-300 hover:border-primary/50 hover:bg-base-200/50'))
      ]"
      @click="openFileDialog"
    >
      <!-- Empty state -->
      <svg v-if="!modelValue && !error" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 opacity-40" viewBox="0 0 20 20" fill="currentColor">
        <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
      </svg>
      <span v-if="!modelValue && !error" class="opacity-40 truncate">
        {{ placeholder ?? t("common.dropDefault") }}
      </span>

      <!-- Error state -->
      <span v-if="error" class="text-error text-xs truncate">{{ error }}</span>

      <!-- Filled state -->
      <svg v-if="modelValue && !error" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 shrink-0 opacity-60" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd" />
      </svg>
      <span
        v-if="modelValue && !error"
        class="truncate min-w-0"
        :title="modelValue"
      >
        {{ fileName }}
      </span>
    </div>

    <!-- Clear button -->
    <button
      v-if="(modelValue || error) && !disabled"
      class="btn btn-xs btn-ghost btn-square absolute right-1 top-1/2 -translate-y-1/2 h-6 w-6"
      :title="t('common.clear')"
      @click.stop="clear"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
      </svg>
    </button>
  </div>
</template>
