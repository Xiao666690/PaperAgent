<template>
  <div v-if="props.role === 'system'" class="message-row flex justify-center">
    <div class="max-w-[72%] rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-700">
      {{ props.content }}
    </div>
  </div>

  <div v-else-if="props.role === 'gpt'" class="message-row flex justify-start">
    <el-card shadow="hover" class="card rounded-3xl">
      <div
        v-if="props.modelLabel"
        class="mb-2 text-xs font-medium text-gray-500"
      >
        {{ props.modelLabel }}
      </div>
      <div v-if="props.searchSteps?.length" class="search-progress" aria-live="polite">
        <div class="progress-title">学术检索进度</div>
        <div v-for="(step, index) in props.searchSteps" :key="`${index}-${step}`" class="progress-step">
          <span class="progress-marker" :class="{ active: index === props.searchSteps.length - 1 && props.searchState !== 'done' }">
            {{ index === props.searchSteps.length - 1 && props.searchState !== 'done' ? '•' : '✓' }}
          </span>
          <span>{{ step }}</span>
        </div>
      </div>
      <div v-if="props.status === 'thinking' && !props.content && !props.searchSteps?.length" class="thinking-state" role="status">
        <span>正在思考</span>
        <span class="thinking-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      </div>
      <div v-else class="render" v-html="renderContent(props.content)" @click="handleCitationClick" />
      <ExternalPaperList v-if="props.externalPapers?.items.length" :result="props.externalPapers" />
      <div v-if="((props.status === 'thinking' || props.status === 'streaming') && props.startedAt) || props.durationMs != null" class="response-time" aria-live="polite">
        <template v-if="props.status === 'thinking' || props.status === 'streaming'">
          {{ props.status === 'thinking' ? '正在思考' : '正在回答' }} {{ formatDuration(Math.max(0, now - (props.startedAt || now))) }}
        </template>
        <template v-else-if="props.durationMs != null">
          思考 {{ formatDuration(props.thinkingMs ?? props.durationMs) }} · {{ props.status === 'error' ? '等待耗时' : '回答耗时' }} {{ formatDuration(props.durationMs) }}
        </template>
      </div>
      <div v-if="props.content.trim() && props.status !== 'thinking' && props.status !== 'streaming'" class="answer-actions">
        <button type="button" class="copy-answer" :disabled="copying" :aria-label="copied ? '回答已复制' : '复制回答'" @click="copyAnswer">
          <Check v-if="copied" :size="14" /><Copy v-else :size="14" />{{ copying ? '复制中…' : copied ? '已复制' : '复制回答' }}
        </button>
        <span class="sr-only" role="status">{{ copied ? '回答已复制到剪贴板' : '' }}</span>
      </div>
    </el-card>
  </div>

  <div v-else class="message-row flex justify-end">
    <el-card shadow="hover" class="back-color card rounded-3xl">
      <div v-if="props.documents?.length" class="attached-papers">
        <span v-for="document in props.documents" :key="document.documentID" class="attached-paper">📄 {{ document.documentName }}</span>
      </div>
      <div class="render" v-html="renderMarkdown(props.content)" />
    </el-card>
  </div>
</template>

<style lang="less" scoped>
@import '@/styles/markdown-styles-light.less';

.back-color {
  background-color: #f4f4f4;
}
.message-row { width: 100%; min-width: 0; overflow: hidden; }
.card { box-sizing: border-box; min-width: 0; max-width: 100%; }
:deep(.card .el-card__body) { min-width: 0; max-width: 100%; overflow: hidden; }
:deep(.render) { min-width: 0; max-width: 100%; overflow-wrap: anywhere; word-break: break-word; }
:deep(.render pre), :deep(.render table) { max-width: 100%; overflow-x: auto; }
:deep(.render table) { display: block; }
:deep(.render img) { max-width: 100%; height: auto; }

:deep(.card) .el-card__body {
  padding: 14px 16px !important;
}

:deep(.card) { border: 1px solid #e8e8ea; border-radius: 16px !important; box-shadow: none !important; transition: border-color .18s ease, background .18s ease; }
:deep(.card:hover) { border-color: #dddde1; }
.back-color { border-color: transparent !important; background: #f3f3f4; }
.attached-papers { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 8px; }
.attached-paper { max-width: 260px; overflow: hidden; padding: 4px 7px; border-radius: 6px; background: #e0ecf7; color: #42698e; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.search-progress { margin: 4px 0 14px; padding: 10px 12px; border-radius: 10px; background: #f5f7fb; }
.progress-title { color: #374151; font-size: 12px; font-weight: 600; margin-bottom: 6px; }
.progress-step { display: flex; align-items: flex-start; gap: 8px; margin-top: 4px; color: #6b7280; font-size: 12px; line-height: 1.5; }
.progress-marker { display: inline-flex; flex: 0 0 14px; color: #2b8a68; font-weight: 700; }
.progress-marker.active { color: #6798c5; animation: thinking-pulse 1.2s ease-in-out infinite; }
.response-time { margin-top: 8px; color: #8b8f92; font-size: 11px; font-variant-numeric: tabular-nums; }
.answer-actions { display: flex; align-items: center; margin-top: 12px; }
.copy-answer { display: inline-flex; align-items: center; gap: 6px; padding: 6px 9px; border: 1px solid var(--pa-border); border-radius: 8px; background: var(--pa-surface); color: var(--pa-secondary); font-size: 12px; cursor: pointer; }
.copy-answer:focus-visible { outline: 2px solid var(--pa-brand); outline-offset: 2px; }
.copy-answer:disabled { cursor: wait; opacity: .65; }
@media(hover:hover) and (pointer:fine) { .copy-answer:hover { color: var(--pa-brand); border-color: var(--pa-control); background: var(--pa-selected); } }

.thinking-state {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 24px;
  color: #6b7280;
  font-size: 14px;
}

.thinking-dots {
  display: inline-flex;
  gap: 3px;
}

.thinking-dots i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #6798c5;
  animation: thinking-pulse 1.2s ease-in-out infinite;
}

.thinking-dots i:nth-child(2) {
  animation-delay: 0.15s;
}

.thinking-dots i:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes thinking-pulse {
  0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-2px); }
}
</style>

<script setup lang="ts">
import { Check, Copy } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { copyArtifact } from '@/views/research/components/artifactExport'
import { ElCard } from 'element-plus'
import { useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'
import type { CitationItem } from '@/api/qa'
import type { ExternalPaperResult } from '@/api/qa'
import ExternalPaperList from './ExternalPaperList.vue'
import type { ChatDocumentSnapshot } from '@/stores/chatHistory'

const props = defineProps<{
  role: string
  content: string
  modelLabel?: string
  citations?: CitationItem[]
  externalPapers?: ExternalPaperResult
  searchStatus?: string
  searchState?: 'preparing' | 'searching' | 'answering' | 'done'
  searchSteps?: string[]
  status?: 'thinking' | 'streaming' | 'done' | 'error'
  startedAt?: number
  thinkingMs?: number
  durationMs?: number
  documents?: ChatDocumentSnapshot[]
}>()

const router = useRouter()
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | undefined
watch(() => props.status, (status) => {
  if (status === 'thinking' || status === 'streaming') {
    if (!timer) timer = setInterval(() => { now.value = Date.now() }, 200)
  } else if (timer) { clearInterval(timer); timer = undefined }
}, { immediate: true })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
const formatDuration = (ms: number) => `${(ms / 1000).toFixed(1)} 秒`
const copying = ref(false)
const copied = ref(false)
let copiedTimer: ReturnType<typeof setTimeout> | undefined
const clipboardMarkdown = new MarkdownIt({ html: false, breaks: true, linkify: true })
const copyAnswer = async () => {
  if (copying.value || !props.content.trim()) return
  copying.value = true
  const answer = props.content
  try {
    await copyArtifact(clipboardMarkdown.render(answer), answer)
    copied.value = true
    clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => { copied.value = false }, 2000)
  } catch {
    ElMessage.error('复制失败，请允许浏览器访问剪贴板后重试')
  } finally { copying.value = false }
}
watch(() => props.content, () => { copied.value = false })
onBeforeUnmount(() => clearTimeout(copiedTimer))

const highlightCode = (str: string, lang: string): string => {
  const language = hljs.getLanguage(lang)
  if (language) {
    try {
      return (
        '<pre class="hljs"><code>' +
        hljs.highlight(lang, str, true).value +
        '</code></pre>'
      )
    } catch (error) {
      console.error(error)
    }
  }
  return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>'
}

const md = new MarkdownIt({
  breaks: true,
  html: true,
  linkify: true,
  typographer: true,
  highlight: highlightCode,
})

const renderMarkdown = (text: string) => {
  return md.render(text)
}

// 把 [C#] 引用替换为可点击链接（携带 knowledgeID/documentID/page）
const renderContent = (text: string) => {
  let processed = text
  if (props.citations?.length) {
    processed = text.replace(/\[(C\d+)\]/g, (match, cid) => {
      const c = props.citations!.find((x) => x.id === cid)
      if (!c) return match
      if (!c.knowledgeID) return match
      const href = router.resolve({ name: 'pdfInfo', params: { knowledgeID: c.knowledgeID, documentID: c.documentID }, query: { page: String(c.page) } }).href
      return `<a class="citation-link" href="${md.utils.escapeHtml(href)}" aria-label="查看引用 ${cid}，第 ${c.page} 页" data-kid="${md.utils.escapeHtml(c.knowledgeID)}" data-doc="${md.utils.escapeHtml(c.documentID)}" data-page="${c.page}">${match}</a>`
    })
  }
  return md.render(processed)
}

const handleCitationClick = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.classList.contains('citation-link')) return
  const kid = target.dataset.kid
  const doc = target.dataset.doc
  const page = target.dataset.page
  if (kid && doc && !e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey) {
    e.preventDefault()
    router.push({
      name: 'pdfInfo',
      params: { knowledgeID: kid, documentID: doc },
      query: { page },
    })
  }
}
</script>
