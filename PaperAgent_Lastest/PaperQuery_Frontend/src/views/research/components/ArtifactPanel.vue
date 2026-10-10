<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'
import { CalendarDays, ExternalLink, FileText, Users, Copy, Download } from 'lucide-vue-next'
import { parseComparisonTable, comparisonColumnLabel, formatComparisonCell } from './comparisonTable'
import { copyArtifact, escapeHTML, exportArtifactWord } from './artifactExport'

interface ArtifactData {
  artifact_id: string
  type: string
  title: string
  data?: Record<string, any>
}

const props = defineProps<{ artifact: ArtifactData }>()

const highlightCode = (str: string, lang: string): string => {
  if (lang && hljs.getLanguage(lang)) {
    try {
      return (
        '<pre class="hljs"><code>' +
        hljs.highlight(lang, str, true).value +
        '</code></pre>'
      )
    } catch (e) {
      console.error(e)
    }
  }
  return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>'
}

const md = new MarkdownIt({
  breaks: true,
  // 模型输出属于不可信内容，不允许注入任意 HTML。
  html: false,
  linkify: true,
  highlight: highlightCode,
})

const markdown = computed(() => {
  const d = props.artifact.data || {}
  return d.markdown || d.report || ''
})

const tableData = computed(() => props.artifact.type === 'comparison_table' ? parseComparisonTable(props.artifact.data || {}) : null)
const artifactLabel = computed(() => ({ comparison_table: '论文对比表', research_report: '研究报告', paper_list: '论文列表' }[props.artifact.type] || props.artifact.type))

const rawText = computed(() => {
  const d = props.artifact.data || {}
  if (typeof d.raw === 'string') return d.raw
  return JSON.stringify(d, null, 2)
})

const papers = computed<Array<Record<string, any>>>(() => {
  if (props.artifact.type !== 'paper_list') return []
  return props.artifact.data?.papers || []
})

const formatAuthors = (authors: unknown) => {
  if (!Array.isArray(authors) || authors.length === 0) return '作者信息暂缺'
  const names = authors.slice(0, 4).join('、')
  return authors.length > 4 ? `${names} 等` : names
}

const copying = ref(false)
const exporting = ref(false)
const exportHTML = computed(() => {
  const title = props.artifact.title || '研究结果'
  let body = ''
  if (props.artifact.type === 'research_report' && markdown.value) body = md.render(markdown.value)
  else if (tableData.value) {
    const {columns, rows} = tableData.value
    body = `<table><thead><tr>${columns.map(col => `<th>${escapeHTML(comparisonColumnLabel(col))}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${columns.map(col => `<td>${escapeHTML(formatComparisonCell(Object.prototype.hasOwnProperty.call(row, col) ? row[col] : undefined)).replace(/\n/g, '<br>')}</td>`).join('')}</tr>`).join('')}</tbody></table>`
  } else if (papers.value.length) {
    body = papers.value.map((paper, i) => `<h2>${i+1}. ${escapeHTML(String(paper.title || '未命名论文'))}</h2><p>作者：${escapeHTML(Array.isArray(paper.authors) ? paper.authors.join('、') : '作者信息暂缺')}</p><p>${escapeHTML(String(paper.published || ''))} · ${escapeHTML(String(paper.venue || paper.provider || ''))}</p><p>${escapeHTML(String(paper.summary || ''))}</p><p>${escapeHTML(String(paper.pdf_url || paper.doi || paper.openalex_id || ''))}</p>`).join('')
  } else body = `<pre>${escapeHTML(rawText.value)}</pre>`
  const content = new DOMParser().parseFromString(body, 'text/html')
  // Avoid repeating the model's report title when it is already the first heading.
  return content.body.firstElementChild?.textContent?.trim() === title.trim() ? body : `<h1>${escapeHTML(title)}</h1>${body}`
})

function copyText() {
  // innerText preserves rendered block/table boundaries; detached textContent does not.
  const container = document.createElement('div')
  container.innerHTML = exportHTML.value
  container.querySelectorAll('a[href]').forEach(link => {
    const url = link.getAttribute('href') || ''
    if (/^https?:\/\//i.test(url) && link.textContent !== url) link.append(document.createTextNode(` (${url})`))
  })
  container.style.cssText = 'position:fixed;left:-9999px;top:0;white-space:normal'
  document.body.append(container)
  try { return container.innerText } finally { container.remove() }
}
async function copyResult() {
  if (copying.value) return
  copying.value = true
  try { await copyArtifact(exportHTML.value, copyText()); ElMessage.success({ message: '研究结果已复制，可粘贴到 Word 或笔记中', grouping: true }) }
  catch { ElMessage.error('复制失败，请允许浏览器访问剪贴板，或使用导出 Word') }
  finally { copying.value = false }
}
async function exportWord() {
  if (exporting.value) return
  exporting.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 0))
    exportArtifactWord(props.artifact.title, exportHTML.value)
    ElMessage.success({ message: 'Word 文件已生成，请查看浏览器下载记录', grouping: true })
  } catch { ElMessage.error('导出失败，请稍后重试') }
  finally { exporting.value = false }
}
</script>

<template>
  <article class="artifact-card">
    <div class="artifact-header">
      <div class="artifact-heading">
        <span class="artifact-icon"><FileText :size="16" /></span>
        <div><small>研究结果</small><strong>{{ artifact.title }}</strong></div>
      </div>
      <div class="artifact-actions">
        <el-tag size="small" effect="light">{{ artifactLabel }}</el-tag>
        <el-button size="small" :loading="copying" :aria-label="`复制结果：${artifact.title}`" @click="copyResult"><Copy v-if="!copying" :size="14" />复制结果</el-button>
        <el-button size="small" type="primary" :loading="exporting" :aria-label="`导出 Word：${artifact.title}`" @click="exportWord"><Download v-if="!exporting" :size="14" />导出 Word</el-button>
      </div>
    </div>

    <!-- Markdown 报告 -->
    <div
      v-if="artifact.type === 'research_report' && markdown"
      class="render"
      v-html="md.render(markdown)"
    />

    <!-- 论文检索结果 -->
    <div v-else-if="papers.length" class="paper-list">
      <a
        v-for="(paper, index) in papers"
        :key="paper.openalex_id || paper.doi || paper.pdf_url || index"
        class="paper-item"
        :href="paper.pdf_url || paper.doi || undefined"
        :target="paper.pdf_url || paper.doi ? '_blank' : undefined"
        rel="noopener noreferrer"
      >
        <span class="paper-index">{{ String(index + 1).padStart(2, '0') }}</span>
        <div class="paper-copy">
          <strong>{{ paper.title || '未命名论文' }}</strong>
          <div class="paper-meta">
            <span><Users :size="12" /> {{ formatAuthors(paper.authors) }}</span>
            <span v-if="paper.published"><CalendarDays :size="12" /> {{ paper.published }}</span>
            <span>来源：{{ paper.venue || (paper.provider === 'arxiv' ? 'arXiv 预印本' : '来源未注明') }}<template v-if="paper.source_type"> · {{ paper.source_type }}</template></span>
          </div>
          <p v-if="paper.summary">{{ paper.summary }}</p>
        </div>
        <ExternalLink v-if="paper.pdf_url || paper.doi" :size="16" class="external-icon" />
      </a>
    </div>

    <!-- 对比表 -->
    <el-table v-else-if="tableData" class="comparison-table" :data="tableData.rows" border max-height="560" empty-text="对比结果暂无数据">
      <el-table-column
        v-for="col in tableData.columns"
        :key="col"
        :prop="col"
        :label="comparisonColumnLabel(col)"
        :min-width="comparisonColumnLabel(col) === '论文' ? 180 : 240"
      >
        <template #default="{ row }"><div class="comparison-cell">{{ formatComparisonCell(Object.prototype.hasOwnProperty.call(row, col) ? row[col] : undefined) }}</div></template>
      </el-table-column>
    </el-table>

    <div v-else-if="artifact.type === 'comparison_table'" class="comparison-fallback">
      <p>这份结果的表格格式暂无法识别，可展开查看原始内容</p>
      <details><summary>查看原始输出</summary><pre class="raw-output">{{ rawText }}</pre></details>
    </div>

    <!-- 其他：展示原始文本 -->
    <pre v-else class="raw-output">{{ rawText }}</pre>
  </article>
</template>

<style scoped>
.artifact-card { overflow: hidden; border: 1px solid #e6e6e8; border-radius: 11px; background: #fff; }
.artifact-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 13px 15px; border-bottom: 1px solid #ececee; background: #fafafa; }.artifact-heading { display: flex; align-items: center; gap: 10px; min-width: 0; }.artifact-icon { display: grid; place-items: center; flex: none; width: 30px; height: 30px; border-radius: 8px; color: #5b97d0; background: #eef3f8; }.artifact-heading small,.artifact-heading strong { display: block; }.artifact-heading small { color: #96999b; font-size: 8px; font-weight: 500; letter-spacing: 0; }.artifact-heading strong { overflow: hidden; margin-top: 2px; color: #3c3e40; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
:deep(.render) { padding: 18px; color: #465169; font-size: 13px; line-height: 1.75; }:deep(.render h1),:deep(.render h2),:deep(.render h3) { color: #253049; }:deep(.render table) { width: 100%; border-collapse: collapse; }:deep(.render th),:deep(.render td) { padding: 8px; border: 1px solid #e3e7f0; }
.paper-list { display: grid; gap: 8px; padding: 12px; }.paper-item { display: flex; align-items: flex-start; gap: 11px; padding: 12px; border: 1px solid #ececee; border-radius: 9px; color: inherit; text-decoration: none; background: #fff; transition: .15s; }.paper-item:hover { border-color: #ccd5de; background: #fafafa; transform: none; box-shadow: none; }.paper-index { display: grid; place-items: center; flex: none; width: 28px; height: 28px; border-radius: 7px; color: #5483af; background: #eef3f8; font-size: 9px; font-weight: 600; }.paper-copy { flex: 1; min-width: 0; }.paper-copy strong { display: block; color: #37393b; font-size: 12px; line-height: 1.5; }.paper-meta { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 6px; color: #8e9193; font-size: 9px; }.paper-meta span { display: flex; align-items: center; gap: 4px; }.paper-copy p { display: -webkit-box; overflow: hidden; margin: 8px 0 0; color: #707375; font-size: 10px; line-height: 1.55; -webkit-box-orient: vertical; -webkit-line-clamp: 3; }.external-icon { flex: none; margin-top: 5px; color: #999c9e; }
.raw-output { overflow: auto; max-height: 420px; margin: 0; padding: 16px; color: #5c667a; background: #fbfcfe; font-size: 11px; line-height: 1.6; white-space: pre-wrap; }
.comparison-table { --el-table-header-bg-color: #edf7ff; --el-table-header-text-color: #285d88; --el-table-border-color: #e1ebf4; --el-table-row-hover-bg-color: #f5faff; }
.comparison-table :deep(.el-table__cell) { vertical-align: top; }
.comparison-cell { padding: 5px 0; color: #40536a; font-size: 13px; line-height: 1.75; white-space: pre-wrap; overflow-wrap: anywhere; }
.comparison-fallback { padding: 16px; color: #6c7e91; font-size: 13px; }.comparison-fallback p { margin: 0 0 12px; }.comparison-fallback summary { color: #147bdf; cursor: pointer; }.comparison-fallback .raw-output { margin-top: 12px; }
.artifact-header { flex-wrap: wrap; }
.artifact-heading { flex: 1 1 220px; }
.artifact-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.artifact-actions .el-button + .el-button { margin-left: 0; }
.artifact-actions .el-button { gap: 5px; }
@media(max-width:650px) { .artifact-actions { width: 100%; }.artifact-actions .el-tag { margin-right: auto; }.artifact-heading strong { white-space: normal; overflow-wrap: anywhere; } }
</style>
