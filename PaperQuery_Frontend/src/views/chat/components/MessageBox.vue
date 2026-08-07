<template>
  <div v-if="props.role === 'system'" class="flex justify-center">
    <div class="max-w-[72%] rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-700">
      {{ props.content }}
    </div>
  </div>

  <div v-else-if="props.role === 'gpt'" class="flex justify-start">
    <el-card shadow="hover" class="card rounded-3xl">
      <div
        v-if="props.modelLabel"
        class="mb-2 text-xs font-medium text-gray-500"
      >
        {{ props.modelLabel }}
      </div>
      <div class="render" v-html="renderMarkdown(props.content)" />
    </el-card>
  </div>

  <div v-else class="flex justify-end">
    <el-card shadow="hover" class="back-color card rounded-3xl">
      <div class="render" v-html="renderMarkdown(props.content)" />
    </el-card>
  </div>
</template>

<style lang="less" scoped>
@import '@/styles/markdown-styles-light.less';

.back-color {
  background-color: #f4f4f4;
}

:deep(.card) .el-card__body {
  padding: 10px !important;
}
</style>

<script setup lang="ts">
import { ElCard } from 'element-plus'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'

const props = defineProps<{
  role: string
  content: string
  modelLabel?: string
}>()

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
</script>
