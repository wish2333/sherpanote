<script setup lang="ts">
/**
 * MindMapPreview - Interactive mind map renderer for Markmap Markdown.
 *
 * Parses Markdown headings into a tree structure and renders
 * as an SVG-based mind map with pan/zoom support.
 * No external dependency required.
 */
import { ref, watch, onMounted, onBeforeUnmount } from "vue";

const props = defineProps<{
  content: string;
}>();

interface TreeNode {
  text: string;
  children: TreeNode[];
  depth: number;
}

const svgRef = ref<SVGSVGElement | null>(null);
const viewBox = ref({ x: 0, y: 0, w: 800, h: 600 });
let isDragging = false;
let dragStart = { x: 0, y: 0 };
let vbStart = { x: 0, y: 0 };

function parseMarkdownToTree(md: string): TreeNode {
  const root: TreeNode = { text: "Mind Map", children: [], depth: 0 };
  const lines = md.split("\n").filter((l) => l.trim());
  const stack: TreeNode[] = [root];

  for (const line of lines) {
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (!headingMatch) continue;

    const depth = headingMatch[1].length;
    const text = headingMatch[2].trim();
    if (!text) continue;

    const node: TreeNode = { text, children: [], depth };

    // Pop stack until we find a parent with lower depth
    while (stack.length > 1 && stack[stack.length - 1].depth >= depth) {
      stack.pop();
    }

    stack[stack.length - 1].children.push(node);
    stack.push(node);
  }

  // If the root only has one top-level child, use it as root
  if (root.children.length === 1) {
    return root.children[0];
  }
  return root;
}

interface LayoutNode {
  text: string;
  x: number;
  y: number;
  children: LayoutNode[];
  depth: number;
}

const NODE_H_GAP = 200;
const NODE_V_GAP = 40;

function layoutTree(node: TreeNode): LayoutNode {
  // Count leaves to determine subtree height
  function countLeaves(n: TreeNode): number {
    if (n.children.length === 0) return 1;
    return n.children.reduce((s, c) => s + countLeaves(c), 0);
  }

  function layout(
    n: TreeNode,
    x: number,
    yStart: number,
    yEnd: number,
  ): LayoutNode {
    const yMid = (yStart + yEnd) / 2;
    const result: LayoutNode = {
      text: n.text,
      x,
      y: yMid,
      children: [],
      depth: n.depth,
    };

    if (n.children.length > 0) {
      const totalLeaves = countLeaves(n);
      const range = yEnd - yStart;
      let currentY = yStart;

      for (const child of n.children) {
        const childLeaves = countLeaves(child);
        const childRange = (childLeaves / totalLeaves) * range;
        result.children.push(
          layout(child, x + NODE_H_GAP, currentY, currentY + childRange),
        );
        currentY += childRange;
      }
    }

    return result;
  }

  const totalLeaves = countLeaves(node);
  const totalHeight = Math.max(totalLeaves * NODE_V_GAP, 200);
  return layout(node, 50, -totalHeight / 2, totalHeight / 2);
}

const renderedNodes = ref<LayoutNode | null>(null);

function render() {
  if (!props.content) {
    renderedNodes.value = null;
    return;
  }

  const tree = parseMarkdownToTree(props.content);
  const layout = layoutTree(tree);
  renderedNodes.value = layout;

  // Auto-fit viewBox
  const bounds = getBounds(layout);
  if (bounds) {
    const pad = 80;
    viewBox.value = {
      x: bounds.minX - pad,
      y: bounds.minY - pad,
      w: bounds.maxX - bounds.minX + pad * 2,
      h: bounds.maxY - bounds.minY + pad * 2,
    };
  }
}

function getBounds(node: LayoutNode): { minX: number; minY: number; maxX: number; maxY: number } | null {
  let minX = node.x;
  let maxX = node.x;
  let minY = node.y;
  let maxY = node.y;

  for (const child of node.children) {
    const cb = getBounds(child);
    if (cb) {
      minX = Math.min(minX, cb.minX);
      maxX = Math.max(maxX, cb.maxX);
      minY = Math.min(minY, cb.minY);
      maxY = Math.max(maxY, cb.maxY);
    }
  }

  return { minX, minY, maxX, maxY };
}

function renderNode(node: LayoutNode): string {
  let svg = "";
  const fontSize = node.depth === 0 ? 14 : node.depth === 1 ? 12 : 11;
  const fontWeight = node.depth <= 1 ? "bold" : "normal";

  // Draw lines to children
  for (const child of node.children) {
    svg += `<line x1="${node.x}" y1="${node.y}" x2="${child.x}" y2="${child.y}" stroke="currentColor" stroke-opacity="0.2" stroke-width="1"/>`;
    svg += renderNode(child);
  }

  // Draw node
  svg += `<text x="${node.x}" y="${node.y}" text-anchor="start" dominant-baseline="middle" font-size="${fontSize}" font-weight="${fontWeight}" fill="currentColor" class="node-text">${escapeXml(node.text)}</text>`;

  return svg;
}

function escapeXml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const svgContent = ref("");

watch(
  () => props.content,
  () => {
    render();
    if (renderedNodes.value) {
      svgContent.value = renderNode(renderedNodes.value);
    }
  },
  { immediate: true },
);

// Pan support
function onMouseDown(e: MouseEvent) {
  isDragging = true;
  dragStart = { x: e.clientX, y: e.clientY };
  vbStart = { x: viewBox.value.x, y: viewBox.value.y };
}

function onMouseMove(e: MouseEvent) {
  if (!isDragging || !svgRef.value) return;
  const svg = svgRef.value;
  const rect = svg.getBoundingClientRect();
  const scaleX = viewBox.value.w / rect.width;
  const scaleY = viewBox.value.h / rect.height;
  viewBox.value.x = vbStart.x - (e.clientX - dragStart.x) * scaleX;
  viewBox.value.y = vbStart.y - (e.clientY - dragStart.y) * scaleY;
}

function onMouseUp() {
  isDragging = false;
}

function onWheel(e: WheelEvent) {
  e.preventDefault();
  const factor = e.deltaY > 0 ? 1.1 : 0.9;
  const newW = viewBox.value.w * factor;
  const newH = viewBox.value.h * factor;
  // Zoom toward mouse position
  if (svgRef.value) {
    const svg = svgRef.value;
    const rect = svg.getBoundingClientRect();
    const mx = (e.clientX - rect.left) / rect.width;
    const my = (e.clientY - rect.top) / rect.height;
    viewBox.value.x += (viewBox.value.w - newW) * mx;
    viewBox.value.y += (viewBox.value.h - newH) * my;
  }
  viewBox.value.w = newW;
  viewBox.value.h = newH;
}

onMounted(() => {
  window.addEventListener("mouseup", onMouseUp);
});

onBeforeUnmount(() => {
  window.removeEventListener("mouseup", onMouseUp);
});
</script>

<template>
  <div class="w-full rounded-lg border border-base-300 bg-base-100 overflow-hidden">
    <div class="px-3 py-2 border-b border-base-300 text-xs text-base-content/50 flex items-center justify-between">
      <span>Mind Map Preview</span>
      <span class="opacity-50">Drag to pan, scroll to zoom</span>
    </div>
    <svg
      v-if="svgContent"
      ref="svgRef"
      class="w-full cursor-grab active:cursor-grabbing text-base-content select-none"
      style="height: 400px;"
      :viewBox="`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @wheel.prevent="onWheel"
      v-html="svgContent"
    ></svg>
    <div v-else class="flex items-center justify-center py-16 text-sm text-base-content/40">
      No mind map content to display
    </div>
  </div>
</template>
