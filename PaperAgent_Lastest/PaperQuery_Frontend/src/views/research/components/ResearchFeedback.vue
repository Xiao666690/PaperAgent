<script setup lang="ts">
import { ref } from 'vue'
import { ThumbsDown, ThumbsUp } from 'lucide-vue-next'
import { researchPreferences, saveResearchFeedback } from '@/api/research'
import type { ResearchFeedback, ResearchPreference } from '@/api/research'

const props = defineProps<{ taskId: string; version: number; feedback?: ResearchFeedback | null }>()
const rating = ref<ResearchFeedback['rating'] | null>(props.feedback?.rating ?? null)
const reason = ref<ResearchFeedback['reason']>(props.feedback?.reason ?? null)
const note = ref(props.feedback?.note ?? '')
const preference = ref<ResearchPreference | null>(props.feedback?.preference ?? null)
const expanded = ref(false)
const saving = ref(false)
const saved = ref(Boolean(props.feedback))
const error = ref('')

const reasons = {
  answer_quality: '结论有误或不够准确',
  missing_evidence: '缺少原文依据',
  incomplete: '回答不完整',
  off_topic: '偏离问题',
  too_verbose: '内容冗长',
}

async function submit(value = rating.value) {
  if (!value || saving.value) return
  rating.value = value
  saving.value = true
  error.value = ''
  try {
    await saveResearchFeedback(props.taskId, props.version, {
      rating: value, reason: reason.value, note: note.value.trim(), preference: preference.value,
    })
    saved.value = true
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '反馈保存失败，请重试'
  } finally {
    saving.value = false
  }
}

function vote(value: ResearchFeedback['rating']) {
  if (rating.value !== value) reason.value = null
  expanded.value = value === 'unsatisfied'
  void submit(value)
}
</script>

<template>
  <section class="research-feedback" aria-label="研究结果反馈">
    <div class="feedback-heading">
      <strong>这次研究结果符合你的预期吗？</strong>
      <div class="feedback-actions">
        <el-button :type="rating === 'satisfied' ? 'primary' : undefined" :aria-pressed="rating === 'satisfied'" :disabled="saving" @click="vote('satisfied')">
          <ThumbsUp :size="15" aria-hidden="true" /> 满意
        </el-button>
        <el-button :type="rating === 'unsatisfied' ? 'primary' : undefined" :aria-pressed="rating === 'unsatisfied'" :disabled="saving" @click="vote('unsatisfied')">
          <ThumbsDown :size="15" aria-hidden="true" /> 不满意
        </el-button>
      </div>
    </div>
    <p v-if="saved" role="status">已记录计划 v{{ version }} 的反馈。</p>
    <button v-if="rating && !expanded" type="button" class="feedback-detail" @click="expanded = true">补充原因或保存输出偏好</button>
    <form v-if="rating && expanded" class="feedback-form" @submit.prevent="submit()">
      <el-select v-if="rating === 'unsatisfied'" v-model="reason" clearable aria-label="不满意原因" placeholder="不满意原因（可选）">
        <el-option v-for="(label, key) in reasons" :key="key" :label="label" :value="key" />
      </el-select>
      <el-input v-model="note" type="textarea" maxlength="1000" aria-label="补充说明" placeholder="哪些结论需要核对，或者哪里还可以改进？" />
      <el-select v-model="preference" clearable :value-on-clear="null" aria-label="后续研究输出偏好" placeholder="为后续研究保存一个输出偏好（可选）">
        <el-option v-for="(label, key) in researchPreferences" :key="key" :label="label" :value="key" />
      </el-select>
      <el-button native-type="submit" :loading="saving">保存反馈</el-button>
    </form>
    <p v-if="error" role="alert" class="feedback-error">{{ error }}</p>
  </section>
</template>

<style scoped>
.research-feedback { display: grid; gap: .55rem; margin-block: .8rem 1.2rem; padding: .75rem 1rem; border: 1px solid #dce6f3; border-radius: .65rem; background: #f7faff; }
.feedback-heading, .feedback-actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: .45rem; }
.feedback-actions .el-button { margin-left: 0; }
.feedback-actions svg { margin-inline-end: .3rem; }
.research-feedback p { margin: 0; font-size: .85rem; }
.feedback-form { display: grid; gap: .55rem; }
.feedback-form .el-button, .feedback-detail { justify-self: start; }
.feedback-detail { color: #315b91; text-decoration: underline; cursor: pointer; }
.research-feedback .feedback-error { color: #ad3535; }
</style>
