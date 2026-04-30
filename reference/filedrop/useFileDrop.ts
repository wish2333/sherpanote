/**
 * File drag-and-drop composable.
 *
 * Manages drag state and integrates with pywebvue's get_dropped_files
 * to retrieve paths from the Python backend after a drop event.
 */

import { ref, onUnmounted } from "vue"
import { call } from "../bridge"

export function useFileDrop() {
  const isDragging = ref(false)
  let dragCounter = 0

  function onDragEnter(e: DragEvent): void {
    e.preventDefault()
    e.stopPropagation()
    dragCounter++
    if (dragCounter === 1) {
      isDragging.value = true
    }
  }

  function onDragOver(e: DragEvent): void {
    e.preventDefault()
    e.stopPropagation()
  }

  function onDragLeave(e: DragEvent): void {
    e.preventDefault()
    e.stopPropagation()
    dragCounter--
    if (dragCounter === 0) {
      isDragging.value = false
    }
  }

  async function onDrop(): Promise<string[]> {
    isDragging.value = false
    dragCounter = 0
    // Wait for pywebvue's document-level drop handler to populate the buffer
    await new Promise((resolve) => setTimeout(resolve, 50))
    const res = await call<string[]>("get_dropped_files")
    return res.success && res.data ? res.data : []
  }

  function reset(): void {
    isDragging.value = false
    dragCounter = 0
  }

  onUnmounted(reset)

  return {
    isDragging,
    onDragEnter,
    onDragOver,
    onDragLeave,
    onDrop,
  }
}
