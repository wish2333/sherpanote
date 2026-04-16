<script setup lang="ts">
/**
 * MarkdownRenderer - Lightweight Markdown-to-HTML renderer.
 *
 * Handles common Markdown constructs from LLM output:
 * headings, bold, italic, strikethrough, lists, code blocks,
 * horizontal rules, links, blockquotes, and tables.
 * No external dependency required.
 */
import { computed } from "vue";

const props = defineProps<{
  content: string;
}>();

const renderedHtml = computed(() => renderMarkdown(props.content));

function renderMarkdown(md: string): string {
  if (!md) return "";

  const lines = md.split("\n");
  const result: string[] = [];
  let inCodeBlock = false;
  let inList = false;
  let listKind = ""; // "ul" | "ol"
  let inBlockquote = false;
  let inTable = false;

  function closeList() {
    if (inList) {
      result.push(listKind === "ol" ? "</ol>" : "</ul>");
      inList = false;
      listKind = "";
    }
  }

  function closeBlockquote() {
    if (inBlockquote) {
      result.push("</blockquote>");
      inBlockquote = false;
    }
  }

  function closeTable() {
    if (inTable) {
      result.push("</tbody></table>");
      inTable = false;
    }
  }

  function isTableRow(line: string): boolean {
    const trimmed = line.trim();
    return trimmed.startsWith("|") && trimmed.endsWith("|");
  }

  function isTableSeparator(line: string): boolean {
    const trimmed = line.trim();
    return /^\|[\s:|-]+\|$/.test(trimmed);
  }

  function parseTableRow(line: string, isHeader: boolean): string {
    const cells = line.trim().slice(1, -1).split("|");
    const tag = isHeader ? "th" : "td";
    const tags = cells.map((cell) => `<${tag}>${inlineFormat(cell.trim())}</${tag}>`);
    return tags.join("");
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code block toggle
    if (line.trimStart().startsWith("```")) {
      if (inCodeBlock) {
        result.push("</code></pre>");
        inCodeBlock = false;
      } else {
        closeList();
        closeBlockquote();
        inCodeBlock = true;
        const lang = line.trimStart().slice(3).trim();
        result.push(`<pre class="not-prose"><code class="${lang ? `language-${lang}` : ""}">`);
      }
      continue;
    }

    if (inCodeBlock) {
      result.push(escapeHtml(line));
      continue;
    }

    // Empty line
    if (line.trim() === "") {
      closeList();
      closeBlockquote();
      closeTable();
      continue;
    }

    // Blockquote
    if (line.trimStart().startsWith("> ")) {
      closeList();
      closeTable();
      if (!inBlockquote) {
        result.push("<blockquote>");
        inBlockquote = true;
      }
      result.push(`<p>${inlineFormat(line.trimStart().slice(2))}</p>`);
      continue;
    } else {
      closeBlockquote();
    }

    // Headings
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      closeList();
      closeTable();
      const level = headingMatch[1].length;
      result.push(`<h${level}>${inlineFormat(headingMatch[2])}</h${level}>`);
      continue;
    }

    // Table
    if (isTableRow(line)) {
      closeList();
      closeBlockquote();
      // Look ahead: if next non-empty line is a separator, this is the header row.
      const isHeader =
        !inTable &&
        i + 1 < lines.length &&
        isTableSeparator(lines[i + 1]);
      if (!inTable) {
        inTable = true;
        if (isHeader) {
          result.push("<table><thead>");
          result.push(`<tr>${parseTableRow(line, true)}</tr>`);
          // The separator row itself will be caught on the next iteration
          // and skipped, switching us to tbody.
          continue;
        }
        result.push("<table><tbody>");
      }
      // Skip separator row; switch from thead to tbody.
      if (isTableSeparator(line)) {
        result.push("</thead><tbody>");
        continue;
      }
      result.push(`<tr>${parseTableRow(line, false)}</tr>`);
      continue;
    } else if (inTable) {
      closeTable();
    }

    // Horizontal rule
    if (/^(\*{3,}|-{3,}|_{3,})\s*$/.test(line.trim())) {
      closeList();
      result.push("<hr>");
      continue;
    }

    // Unordered list
    const ulMatch = line.match(/^(\s*)([-*+])\s+(.+)$/);
    if (ulMatch) {
      if (!inList || listKind !== "ul") {
        closeList();
        inList = true;
        listKind = "ul";
        result.push("<ul>");
      }
      result.push(`<li>${inlineFormat(ulMatch[3])}</li>`);
      continue;
    }

    // Ordered list
    const olMatch = line.match(/^(\s*)\d+\.\s+(.+)$/);
    if (olMatch) {
      if (!inList || listKind !== "ol") {
        closeList();
        inList = true;
        listKind = "ol";
        result.push("<ol>");
      }
      result.push(`<li>${inlineFormat(olMatch[2])}</li>`);
      continue;
    }

    // Paragraph
    closeList();
    result.push(`<p>${inlineFormat(line)}</p>`);
  }

  closeList();
  closeBlockquote();
  closeTable();

  return result.join("\n");
}

function inlineFormat(text: string): string {
  // Bold + italic
  text = text.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  // Bold
  text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Italic
  text = text.replace(/\*(.+?)\*/g, "<em>$1</em>");
  // Strikethrough
  text = text.replace(/~~(.+?)~~/g, "<del>$1</del>");
  // Inline code
  text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
  // Links
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="link link-primary" target="_blank">$1</a>');
  return text;
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
</script>

<template>
  <div
    class="prose prose-sm max-w-none text-base-content"
    v-html="renderedHtml"
  ></div>
</template>
