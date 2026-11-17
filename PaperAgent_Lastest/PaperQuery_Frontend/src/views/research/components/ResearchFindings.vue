<script setup lang="ts">
import type { ResearchFinding } from '@/api/research'

defineProps<{ findings: ResearchFinding[] }>()
</script>

<template>
  <ul v-if="findings.length" class="research-findings">
    <li v-for="(finding, index) in findings" :key="index">
      <p>{{ finding.text }}</p>
      <blockquote v-for="(reference, refIndex) in finding.references" :key="refIndex">
        <a v-if="reference.url" :href="reference.url" target="_blank" rel="noopener noreferrer">{{ reference.title }}</a>
        <RouterLink
          v-else
          :to="{
            name: 'pdfInfo',
            params: { knowledgeID: reference.knowledge_id, documentID: reference.document_id },
            query: { page: String(reference.page) },
          }"
          target="_blank"
          rel="noopener"
        >{{ reference.title }} · 第 {{ reference.page }} 页</RouterLink>
        <p v-if="reference.quote">{{ reference.quote }}</p>
      </blockquote>
    </li>
  </ul>
</template>

<style scoped>
.research-findings { padding-inline-start: 1.25rem; overflow-wrap: anywhere; }
.research-findings li + li { margin-top: .7rem; }
.research-findings p { margin: .25rem 0; }
blockquote { margin: .4rem 0; border-inline-start: 2px solid #cbd5e1; padding-inline-start: .65rem; color: #475569; }
a { color: #315baf; text-decoration: underline; }
</style>
