<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, ClipboardCheck, Clock3, Search } from 'lucide-vue-next'
import { normalizedCriteria, researchDifficultyLabels, researchSearchScopeLabels, validResearchQuestion } from '@/api/research'
import type { GuidedStep, ResearchBudget, ResearchDifficulty, ResearchQuestion, ResearchReview, ResearchReviewPolicy, ResearchSource } from '@/api/research'
import ResearchFindings from './ResearchFindings.vue'

const props = defineProps<{
  version: number
  steps: GuidedStep[]
  currentId?: string | null
  busy: boolean
  documents?: Array<{ id: string; title: string }>
  source?: ResearchSource
  webSearchConfigured?: boolean | null
  difficulty?: ResearchDifficulty
  assessment?: { difficulty: ResearchDifficulty | null; reason: string } | null
  reviewPolicy?: ResearchReviewPolicy
  budgets?: Record<ResearchDifficulty, ResearchBudget>
  objective?: string | null
}>()
const emit = defineEmits<{ submit: [review: Omit<ResearchReview, 'revision'>] }>()
const current = computed(() => props.steps.find(step => step.step_id === props.currentId))
const future = computed(() => props.steps.filter(step => !step.reviewed && step.step_id !== props.currentId))
const editableSteps = computed(() => props.steps.filter(step => step.reviewed || step.step_id === props.currentId))
const visibleSteps = computed(() => editing.value ? editableSteps.value : props.steps)
const editing = ref(false)
const questions = ref<ResearchQuestion[]>([])
const query = ref('')
const difficulty = ref<ResearchDifficulty>(props.difficulty ?? 'standard')
const reviewPolicy = ref<ResearchReviewPolicy>(props.reviewPolicy ?? 'all')
const objective = ref(props.objective ?? '')
const selectedBudget = computed(() => props.budgets?.[difficulty.value])
const effortLabels = { none: '直接整理', low: '轻量推理', high: '深入推理' }

function approve(action: 'continue' | 'revise') {
  emit('submit', {
    action,
    ...(action === 'revise' ? { questions: questions.value.map(question => ({
      ...question, criteria: normalizedCriteria(question.criteria),
    })) } : {}),
    ...(!current.value || future.value.length ? { difficulty: difficulty.value } : {}),
    ...(!current.value ? {
      review_policy: reviewPolicy.value,
      objective: objective.value.trim() || undefined,
    } : {}),
  })
}

function editPlan() {
  questions.value = future.value.map(({ title, query, criteria, search_scope }) => ({ title, query, criteria: [...(criteria ?? [])], search_scope }))
  editing.value = true
}

const validPlan = computed(() =>
  Boolean(questions.value.length || current.value) &&
  questions.value.every(validResearchQuestion),
)
</script>

<template>
  <div class="review-content">
    <div class="review-scroll">
      <div class="review-context">
        <p v-if="source === 'discovery'"><strong>研究范围</strong> 公开来源</p>
        <p v-else-if="documents?.length">
          <strong>研究范围</strong> {{ documents.map(item => item.title).join('、') }}
        </p>
        <p>{{ editing ? '计划草稿' : `计划 v${version}` }} · {{ visibleSteps.length + (editing ? questions.length : 0) }} 步</p>
        <p v-if="source === 'discovery' && webSearchConfigured === false" class="budget-caption">本机尚未配置网页搜索。当前可用的公开检索渠道为学术索引。</p>
      </div>
      <section v-if="!current && budgets" class="review-assessment">
        <p v-if="props.objective"><strong>Agent 对任务的理解</strong></p>
        <el-input v-if="props.objective" v-model="objective" type="textarea" :rows="2" maxlength="4000" aria-label="修正任务理解" :disabled="busy" />
        <p v-if="assessment"><strong>{{ assessment.difficulty ? `Agent 建议 · ${researchDifficultyLabels[assessment.difficulty]}` : '难度待确认' }}</strong> · {{ assessment.reason }}</p>
        <el-radio-group v-model="difficulty" aria-label="执行难度" :disabled="busy">
          <el-radio-button v-for="(label, level) in researchDifficultyLabels" :key="level" :value="level">{{ label }}</el-radio-button>
        </el-radio-group>
        <p v-if="selectedBudget" class="budget-caption">
          {{ effortLabels[selectedBudget.effort] }} · 首段输出基础等待 {{ selectedBudget.first_output_seconds }} 秒 · 输出间隔上限 {{ selectedBudget.idle_seconds }} 秒
          · 根据输入和输出进展续时 · 每步自动{{ source === 'discovery' ? '重查' : '补证' }} {{ selectedBudget.automatic_repairs }} 次
        </p>
        <el-checkbox v-model="reviewPolicy" true-value="checkpoints" false-value="all" :disabled="busy">
          仅在{{ source === 'discovery' ? '检索' : '证据' }}有缺口或准备交付时暂停审批
        </el-checkbox>
      </section>
      <section v-else-if="current && future.length" class="review-assessment">
        <p><strong>后续节点的执行难度</strong></p>
        <el-radio-group v-model="difficulty" aria-label="后续节点的执行难度" :disabled="busy">
          <el-radio-button v-for="(label, level) in researchDifficultyLabels" :key="level" :value="level">{{ label }}</el-radio-button>
        </el-radio-group>
      </section>
      <ol class="review-plan" role="list" aria-label="研究计划步骤">
        <li
          v-for="(step, index) in visibleSteps"
          :key="step.step_id"
          class="review-node"
          :class="{ 'is-current': step.step_id === currentId, 'is-reviewed': step.reviewed }"
          :aria-current="step.step_id === currentId ? 'step' : undefined"
        >
          <span class="review-number">STEP {{ index + 1 }}</span>
          <div class="review-card">
            <div class="review-card-heading">
              <h3>{{ step.title }}</h3>
              <span class="review-status">
                <Check v-if="step.reviewed" :size="14" aria-hidden="true" />
                <ClipboardCheck v-else-if="step.step_id === currentId" :size="14" aria-hidden="true" />
                <Clock3 v-else :size="14" aria-hidden="true" />
                {{ step.review_mode === 'automatic' ? '超时继续' : step.review_mode === 'checkpoint_skipped' ? '已完成并继续' : step.reviewed ? '已审阅' : step.step_id === currentId ? '待审阅' : '待执行' }}
              </span>
            </div>
            <p class="review-query"><Search :size="15" aria-hidden="true" /><span><strong>检索查询</strong> {{ step.query }}</span></p>
            <p v-if="source === 'discovery'" class="review-query">检索渠道 · {{ researchSearchScopeLabels[step.search_scope ?? 'auto'] }}</p>
            <ul v-if="step.criteria?.length" class="review-criteria" aria-label="验收要求">
              <li v-for="(criterion, criterionIndex) in step.criteria" :key="criterionIndex">{{ criterion }}</li>
            </ul>
            <div v-if="current && step.step_id === currentId" class="review-evidence">
              <p>
                <strong v-if="current.status === 'FAILED'">执行异常</strong>
                <strong v-else-if="source === 'discovery'">{{ current.quality === 'VERIFIED' ? '检索整理完成' : '本轮未找到可整理内容' }}</strong>
                <strong v-else>{{ current.quality === 'VERIFIED' ? '证据核验通过' : '仍有证据缺口' }}</strong>
                <span v-if="current.reason"> · {{ current.reason }}</span>
              </p>
              <p v-if="current.missing_criteria?.length">{{ source === 'discovery' ? '本轮未覆盖' : '尚未回答' }} · {{ current.missing_criteria.join('、') }}</p>
              <ResearchFindings :findings="current.findings" />
              <ul v-if="current.papers?.length">
                <li v-for="(paper, paperIndex) in current.papers" :key="paperIndex">{{ paper.title || '未命名候选论文' }}</li>
              </ul>
              <form v-if="current.attempts.length < 5" class="review-repair" @submit.prevent="emit('submit', { action: 'repair', query: query.trim() })">
                <el-input v-model="query" maxlength="300" aria-label="补充查询" placeholder="输入新的检索关键词" />
                <el-button native-type="submit" :disabled="busy || !query.trim()">{{ source === 'discovery' ? '重新检索并整理' : '补证并复核' }}</el-button>
              </form>
            </div>
          </div>
        </li>
        <template v-if="editing">
          <li v-for="(question, index) in questions" :key="index" class="review-node">
            <span class="review-number">STEP {{ visibleSteps.length + index + 1 }}</span>
            <div class="review-card review-edit">
              <el-input v-model="question.title" maxlength="240" :aria-label="`STEP ${visibleSteps.length + index + 1} 研究问题`" placeholder="研究问题" />
              <el-input v-model="question.query" maxlength="300" :aria-label="`STEP ${visibleSteps.length + index + 1} 检索查询`" placeholder="检索查询" />
              <el-select v-if="source === 'discovery'" v-model="question.search_scope" aria-label="检索渠道" placeholder="按问题选择">
                <el-option v-for="(label, scope) in researchSearchScopeLabels" :key="scope" :label="label" :value="scope" />
              </el-select>
              <el-input
                type="textarea" :rows="2" maxlength="1000" :model-value="question.criteria?.join('\n') ?? ''"
                :aria-label="`STEP ${visibleSteps.length + index + 1} 验收要求`" placeholder="验收要求（每行一项，最多 5 项）"
                @update:model-value="value => { question.criteria = value.split('\n') }"
              />
              <el-button :disabled="busy" @click="questions.splice(index, 1)">移除</el-button>
            </div>
          </li>
        </template>
      </ol>
      <el-button v-if="editing" :disabled="busy || questions.length >= 30" @click="questions.push({ title: '', query: '' })">添加节点</el-button>
    </div>
    <div class="review-actions">
      <el-button v-if="!editing" :disabled="busy" @click="editPlan">{{ current ? '修改后续计划' : '修改计划' }}</el-button>
      <el-button v-else :disabled="busy" @click="editing = false">返回</el-button>
      <el-button
        v-if="editing"
        type="primary"
        :loading="busy"
        :disabled="!validPlan"
        @click="approve('revise')"
      >保存并继续</el-button>
      <el-button v-else type="primary" :loading="busy" @click="approve('continue')">
        {{ !current ? '确认计划并开始' : future.length ? '按原计划继续' : '确认并交付' }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.review-content { overflow-wrap: anywhere; }
.review-scroll { max-height: min(64vh, 38rem); max-height: min(64dvh, 38rem); overflow-y: auto; overscroll-behavior: contain; padding-inline-end: .35rem; }
.review-context { display: flex; flex-wrap: wrap; justify-content: space-between; gap: .3rem 1rem; margin-bottom: .9rem; color: #526079; }
.review-context p { margin: 0; }
.review-assessment { margin-bottom: .9rem; padding: .65rem .8rem; border: 1px solid #dbe7f7; border-radius: .65rem; background: #f4f8ff; }
.review-assessment p { margin: 0 0 .45rem; }
.review-assessment .el-textarea { margin-bottom: .65rem; }
.review-criteria { margin: .5rem 0 0; padding-inline-start: 1.25rem; color: #40536c; font-size: .82rem; }
.review-assessment .budget-caption { margin: .45rem 0 0; font-size: .8rem; color: #526079; }
.review-context strong, .review-query strong { margin-inline-end: .35rem; }
.review-plan { list-style: none; padding: 0; margin: 0 0 .25rem; }
.review-node { position: relative; display: grid; grid-template-columns: 4.1rem minmax(0, 1fr); align-items: start; gap: .75rem; padding-bottom: .7rem; }
.review-node:not(:last-child)::before { content: ''; position: absolute; inset: 1.9rem auto -.65rem 2rem; width: 2px; background: #dce6f4; }
.review-number { position: relative; align-self: start; margin-top: .65rem; padding: .32rem .2rem; text-align: center; border-radius: .5rem; background: #eaf2ff; color: #294d85; font: 700 .75rem/1.2 var(--el-font-family, sans-serif); font-variant-numeric: tabular-nums; letter-spacing: .035em; }
.review-card { min-width: 0; padding: .72rem .85rem; border: 1px solid #e1e8f2; border-radius: .7rem; background: #f9fbfe; }
.review-card-heading { display: flex; align-items: start; justify-content: space-between; flex-wrap: wrap; gap: .35rem .75rem; }
.review-card h3 { flex: 1 1 12rem; margin: 0; color: #1d2940; font-size: .95rem; font-weight: 650; line-height: 1.45; }
.review-status { display: inline-flex; align-items: center; gap: .3rem; padding: .2rem .45rem; color: #475569; background: #edf1f6; border-radius: .4rem; white-space: nowrap; font-size: .75rem; line-height: 1.35; }
.review-query { display: flex; align-items: baseline; gap: .45rem; margin: .45rem 0 0; color: #526079; font-size: .83rem; }
.review-query svg { flex: none; align-self: start; margin-top: .12rem; }
.is-current .review-card { border-color: #80b0ef; background: #f3f8ff; }
.is-current .review-number { background: #2463b5; color: white; }
.is-current .review-status { background: #dfeeff; color: #1f5297; }
.is-reviewed .review-number, .is-reviewed .review-status { background: #e9f5ee; color: #246044; }
.review-evidence { border-top: 1px solid #dbe7f7; margin-top: .65rem; padding-top: .65rem; }
.review-evidence > p { margin: 0; }
.review-repair, .review-edit, .review-actions { display: flex; flex-wrap: wrap; align-items: center; gap: .55rem; margin-top: .65rem; }
.review-edit { margin-top: 0; }
.review-repair .el-input, .review-edit .el-input { flex: 1 1 12rem; }
.review-actions { justify-content: flex-end; border-top: 1px solid #e1e8f2; padding-top: .85rem; }
.review-actions .el-button { margin-left: 0; }
@media (max-width: 480px) {
  .review-node { grid-template-columns: 3.5rem minmax(0, 1fr); gap: .45rem; }
  .review-node:not(:last-child)::before { inset-inline-start: 1.7rem; }
  .review-card { padding: .65rem; }
}
</style>
