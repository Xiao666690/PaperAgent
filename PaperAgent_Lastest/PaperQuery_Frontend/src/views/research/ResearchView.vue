<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { ElNotification } from 'element-plus'
import {
  AlertCircle,
  ArrowUpRight,
  BookOpenCheck,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  FileSearch,
  FlaskConical,
  RefreshCw,
  Sparkles,
  XCircle,
} from 'lucide-vue-next'
import {
  createResearchTask,
  listResearchTasks,
  getResearchTask,
  reviewResearchTask,
  researchDifficultyLabels,
  researchPreferences,
  researchSearchScopeLabels,
  normalizedCriteria,
  validResearchQuestion,
} from '@/api/research'
import type { GuidedStep, ResearchBudget, ResearchDifficulty, ResearchFeedback as FeedbackData, ResearchPreference, ResearchQuestion, ResearchReview, ResearchReviewPolicy, ResearchSource } from '@/api/research'
import ArtifactPanel from './components/ArtifactPanel.vue'
import ResearchFeedback from './components/ResearchFeedback.vue'
import ResearchFindings from './components/ResearchFindings.vue'
import ResearchReviewDialog from './components/ResearchReviewDialog.vue'
import { trackResearchTask } from '@/services/taskCompletion'
const route = useRoute()
const router = useRouter()

interface TaskItem {
  task_id: string
  goal: string
  status: string
  mode: string
  created_at?: string
  updated_at?: string
  parent_task_id?: string
}

interface StepInfo {
  step_id: string
  title?: string
  skill_name: string
  status: string
  error?: string
  duration_ms?: number
  guided?: GuidedStep
}

interface ArtifactInfo {
  artifact_id: string
  type: string
  title: string
  data?: Record<string, any>
}

interface TaskDetail {
  task_id: string
  goal: string
  status: string
  created_at?: string
  updated_at?: string
  plan?: { steps: Array<{ step_id: string; title: string; skill?: string }> }
  steps: Array<StepInfo | GuidedStep>
  artifacts: ArtifactInfo[]
  guided?: boolean
  revision?: number
  source?: ResearchSource
  web_search_configured?: boolean | null
  source_unavailable?: boolean
  documents?: Array<{ id: string; title: string }>
  plan_version?: number
  review_step_id?: string | null
  review_deadline?: string | null
  archived_runs?: Array<{ plan_version: number; from_step: number; difficulty?: ResearchDifficulty; steps: GuidedStep[] }>
  plan_history?: Array<{ version: number; reason: string; objective?: string; steps: Array<ResearchQuestion & { step_id: string }> }>
  events?: Array<{ id: number; at: string; title: string; detail: string; plan_version: number; step_id?: string | null }>
  difficulty?: ResearchDifficulty
  assessment?: { difficulty: ResearchDifficulty | null; reason: string } | null
  review_policy?: ResearchReviewPolicy
  active_seconds?: number
  budgets?: Record<ResearchDifficulty, ResearchBudget>
  feedback?: FeedbackData | null
  preference?: ResearchPreference
  objective?: string | null
}

const goal = ref('')
const reviewOpen = ref(false)
const reviewBusy = ref(false)
const rewindOpen = ref(false)
const rewindStepId = ref('')
const rewindQuestions = ref<ResearchQuestion[]>([])
const rewindDifficulty = ref<ResearchDifficulty>('standard')
const offeredReviews = new Map<string, string | undefined>()
const creating = ref(false)
const tasks = ref<TaskItem[]>([])
const currentTask = ref<TaskDetail | null>(null)
const expandedSteps = ref(new Set<string>())
const loadingDetail = ref(false)
const historyCollapsed = ref(true)
const parentTaskId = ref('')
const clock = ref(Date.now())
let clockTimer: ReturnType<typeof setInterval> | undefined
let pollTimer: ReturnType<typeof setInterval> | undefined
let polling = false
let detailRequest = 0

const isActive = (status?: string) => status === 'PENDING' || status === 'QUEUED' || status === 'RUNNING'
const needsReview = (status?: string) => status === 'AWAITING_APPROVAL' || status === 'AWAITING_INPUT'
const canCreate = computed(() => Boolean(goal.value.trim()) && !creating.value)
const guidedSteps = computed(() => currentTask.value?.steps.filter((step): step is GuidedStep => 'quality' in step) ?? [])
const verifiedSteps = computed(() => guidedSteps.value.filter(step => step.quality === 'VERIFIED').length)
const latestEvent = computed(() => currentTask.value?.events?.at(-1))
const taskArtifacts = computed(() => currentTask.value?.artifacts ?? [])
const reports = computed(() => taskArtifacts.value.filter(artifact => artifact.type === 'research_report'))
const mainReport = computed(() =>
  reports.value.find(artifact => artifact.data?.origin === 'reviewed_defense_version') ?? reports.value[0],
)
const supportingArtifacts = computed(() => taskArtifacts.value.filter(artifact => artifact.type !== 'research_report'))
const mainDeliverables = computed(() => mainReport.value ? [mainReport.value] : supportingArtifacts.value)
const nodeOutcomeTitles = new Set([
  '节点核验通过', '节点检索完成', '已记录证据缺口', '已记录检索缺口', '节点执行异常',
])
const keyEventTitles = new Set([
  '任务已创建', '计划已更新', '用户按原计划继续', '用户审阅节点', '审阅超时，按原计划继续',
  '用户调整执行难度', '用户调整审批方式', '用户要求补证', '用户要求重新检索',
  '用户回退并修改计划', '用户回退并按原计划重做', '用户停止任务', '用户恢复研究',
  '用户重试计划生成', '从检查点恢复', '输出中断，等待继续', '论文范围已变化', '任务已达到执行次数上限',
  '综述初稿已生成', '已交付文献综述', '已交付文献综述初稿',
  '报告初稿已生成', '已交付研究报告', '已交付研究初稿', ...nodeOutcomeTitles,
  '研究发现已整理', '已交付阶段性结果',
])
const keyTaskEvents = computed(() => {
  const events = (currentTask.value?.events ?? []).filter(item => keyEventTitles.has(item.title))
  return events.filter((item, index) => {
    const previous = events[index - 1]
    const next = events[index + 1]
    if (item.title === '用户按原计划继续' && previous?.title === '用户审阅节点' &&
        previous.plan_version === item.plan_version) return false
    return !(nodeOutcomeTitles.has(item.title) && item.step_id && next?.step_id === item.step_id &&
      next.plan_version === item.plan_version && next.title === item.title)
  })
})
const stepLabelsByVersion = computed(() => {
  const labels = new Map<number, Map<string, string>>()
  for (const plan of currentTask.value?.plan_history ?? []) {
    labels.set(plan.version, new Map(
      plan.steps.map((step, index) => [step.step_id, `STEP ${index + 1} · ${step.title}`]),
    ))
  }
  const currentVersion = currentTask.value?.plan_version
  if (currentVersion != null && !labels.has(currentVersion)) {
    labels.set(currentVersion, new Map(
      guidedSteps.value.map((step, index) => [step.step_id, `STEP ${index + 1} · ${step.title}`]),
    ))
  }
  return labels
})

function eventStepLabel(version: number, stepId: string) {
  return stepLabelsByVersion.value.get(version)?.get(stepId) ?? `节点 ${stepId}`
}

const reviewSeconds = computed(() => {
  const deadline = currentTask.value?.review_deadline
  return deadline ? Math.max(0, Math.ceil((Date.parse(deadline) - clock.value) / 1000)) : null
})
const rewindIndex = computed(() => guidedSteps.value.findIndex(step => step.step_id === rewindStepId.value))
const reviewKey = computed(() => currentTask.value && needsReview(currentTask.value.status) && !currentTask.value.source_unavailable
  ? `${currentTask.value.task_id}:${currentTask.value.revision}`
  : '')
watch(reviewKey, key => { reviewOpen.value = Boolean(key) && !rewindOpen.value })
watch(() => currentTask.value?.task_id, () => {
  expandedSteps.value.clear()
  rewindOpen.value = false
})

function openRewind(stepId: string) {
  const index = guidedSteps.value.findIndex(step => step.step_id === stepId)
  if (index < 0) return
  rewindStepId.value = stepId
  rewindQuestions.value = guidedSteps.value.slice(index).map(({ title, query, criteria, search_scope }) => ({ title, query, criteria, search_scope }))
  rewindDifficulty.value = currentTask.value?.difficulty ?? 'standard'
  reviewOpen.value = false
  rewindOpen.value = true
}

function toggleStepDetails(stepId: string) {
  if (expandedSteps.value.has(stepId)) expandedSteps.value.delete(stepId)
  else expandedSteps.value.add(stepId)
}

const elapsedTime = (createdAt?: string) => {
  if (!createdAt) return '0 秒'
  const seconds = Math.max(0, Math.floor((clock.value - new Date(createdAt).getTime()) / 1000))
  if (seconds < 60) return `${seconds} 秒`
  return `${Math.floor(seconds / 60)} 分 ${String(seconds % 60).padStart(2, '0')} 秒`
}
const hasRecentActivity = (updatedAt?: string) =>
  Boolean(updatedAt && clock.value - new Date(updatedAt).getTime() < 20000)

const quickGoals = [
  '检索并比较近三年多模态大模型的代表性方法与数据集',
  '梳理时间序列预测领域的主流技术路线并生成综述',
  '分析 RAG 系统的评估指标、常用基准与研究趋势',
]

const successfulTasks = computed(
  () => tasks.value.filter((task) => task.status === 'SUCCESS').length,
)
const failedTasks = computed(() => tasks.value.filter(task => task.status === 'FAILED'))
const completedSteps = computed(
  () => currentTask.value?.guided
    ? guidedSteps.value.filter(step => step.reviewed).length
    : currentTask.value?.steps.filter(step => step.status === 'SUCCESS').length || 0,
)
const displaySteps = computed<StepInfo[]>(() => {
  if (!currentTask.value) return []
  if (currentTask.value.guided) {
    return guidedSteps.value.map(step => ({
      step_id: step.step_id, title: step.title, status: step.status, skill_name: '', guided: step,
    }))
  }
  const legacySteps = currentTask.value.steps.filter((step): step is StepInfo => 'skill_name' in step)
  const planned = (currentTask.value.plan?.steps || []).map(step => ({
    ...legacySteps.find(result => result.step_id === step.step_id),
    step_id: step.step_id,
    title: step.title,
    skill_name: step.skill || '',
    status: legacySteps.find(result => result.step_id === step.step_id)?.status || 'PENDING',
  }))
  const unplanned = legacySteps.filter(result => !planned.some(step => step.step_id === result.step_id))
  return [...planned, ...unplanned]
})
const currentProgress = computed(() => {
  const total = currentTask.value?.plan?.steps?.length || currentTask.value?.steps.length || 0
  return total ? Math.round((completedSteps.value / total) * 100) : 0
})

const getErrorMessage = (error: any, fallback: string) =>
  error?.response?.data?.detail || error?.response?.data?.msg || error?.message || fallback

const loadTasks = async () => {
  try {
    const resp = await listResearchTasks()
    if (resp?.data) {
      tasks.value = resp.data
      if (!currentTask.value && tasks.value.length > 0) {
        const requested = typeof route.query.task === 'string' ? route.query.task : ''
        await selectTask(tasks.value.find(task => task.task_id === requested)?.task_id || tasks.value[0].task_id)
      }
    }
  } catch (e: any) {
    if (e?.response?.status !== 401) console.error(e)
  }
}

const handleCreate = async () => {
  if (!canCreate.value) return
  creating.value = true
  try {
    const resp = await createResearchTask(goal.value.trim(), 'research', [], parentTaskId.value || undefined, 'auto')
    if (resp?.data) {
      trackResearchTask(resp.data)
      ElNotification.success(`任务已创建：${resp.data.task_id}`)
      goal.value = ''
      parentTaskId.value = ''
      await loadTasks()
      await selectTask(resp.data.task_id)
      await router.replace({ query: { ...route.query, task: resp.data.task_id } })
    }
  } catch (e: any) {
    if (e?.response?.status !== 401) ElNotification.error({ title: '创建失败', message: getErrorMessage(e, '任务创建失败') })
  } finally {
    creating.value = false
  }
}

const retryTask = async (task: Pick<TaskItem, 'task_id' | 'goal'>) => {
  if (creating.value) return
  goal.value = task.goal
  parentTaskId.value = task.task_id
  await handleCreate()
}

const continueFromTask = (task: TaskDetail) => {
  parentTaskId.value = task.task_id
  goal.value = task.status === 'NO_RESULTS' ? task.goal : `基于“${task.goal}”的研究结果，进一步研究：`
  document.querySelector('.hero-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const focusTask = async (taskId: string) => {
  await selectTask(taskId)
  document.getElementById('research-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const focusArtifact = (artifactId: string) => {
  document.getElementById(`artifact-${artifactId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

const selectTask = async (taskId: string, quiet = false) => {
  const request = ++detailRequest
  if (!quiet) loadingDetail.value = true
  try {
    const resp = await getResearchTask(taskId)
    if (resp?.data && request === detailRequest) {
      currentTask.value = resp.data
      if (resp.data.status === 'AWAITING_INPUT') offeredReviews.set(taskId, resp.data.updated_at)
    }
  } catch (e: any) {
    if (!quiet && request === detailRequest && e?.response?.status !== 401) {
      ElNotification.error({ title: '加载失败', message: getErrorMessage(e, '任务详情加载失败') })
    }
  } finally {
    if (request === detailRequest) loadingDetail.value = false
  }
}

const submitReview = async (review: Omit<ResearchReview, 'revision'>) => {
  const task = currentTask.value
  if (!task || task.revision === undefined || reviewBusy.value) return
  reviewBusy.value = true
  try {
    await reviewResearchTask(task.task_id, { ...review, revision: task.revision })
    if (currentTask.value?.task_id === task.task_id) {
      reviewOpen.value = false
      if (review.action === 'rewind') rewindOpen.value = false
      await selectTask(task.task_id, true)
    }
    await loadTasks()
  } catch (error: any) {
    if (error?.response?.status !== 401) ElNotification.error({ title: '操作未完成', message: getErrorMessage(error, '请重试') })
    if (error?.response?.status === 409 && currentTask.value?.task_id === task.task_id) {
      await selectTask(task.task_id, true)
    }
  } finally {
    reviewBusy.value = false
  }
}

const statusType = (status: string): 'success' | 'danger' | 'warning' | 'info' => {
  if (status === 'SUCCESS') return 'success'
  if (status === 'FAILED') return 'danger'
  if (status === 'RUNNING' || needsReview(status) || status === 'PARTIAL') return 'warning'
  return 'info'
}

const statusLabel = (status: string) => {
  if (status === 'SUCCESS') return '已完成'
  if (status === 'FAILED') return '执行失败'
  if (status === 'RUNNING') return '执行中'
  if (status === 'PENDING' || status === 'QUEUED') return '排队中'
  if (status === 'AWAITING_APPROVAL') return '待确认计划'
  if (status === 'AWAITING_INPUT') return '待审阅节点'
  if (status === 'WAITING_RETRY') return '输出中断，待继续'
  if (status === 'PARTIAL') return '部分完成'
  if (status === 'NO_RESULTS') return '暂无结果'
  if (status === 'CANCELLED') return '已停止'
  return '等待中'
}

const formatTime = (value?: string) => {
  if (!value) return '刚刚'
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(() => {
  loadTasks()
  clockTimer = setInterval(() => { clock.value = Date.now() }, 1000)
  pollTimer = setInterval(async () => {
    if (polling || loadingDetail.value || reviewBusy.value ||
      !tasks.value.some(task => isActive(task.status) || needsReview(task.status))) return
    polling = true
    try {
      await loadTasks()
      const pending = tasks.value.find(task => task.status === 'AWAITING_INPUT' &&
        (!offeredReviews.has(task.task_id) || offeredReviews.get(task.task_id) !== task.updated_at))
      if (pending && !rewindOpen.value && !reviewOpen.value && !reviewBusy.value && !loadingDetail.value) {
        await selectTask(pending.task_id, true)
        return
      }
      if (!reviewBusy.value && !loadingDetail.value && currentTask.value && (isActive(currentTask.value.status) || needsReview(currentTask.value.status))) {
        await selectTask(currentTask.value.task_id, true)
      }
    } finally { polling = false }
  }, 3000)
})
onBeforeUnmount(() => { clearInterval(clockTimer); clearInterval(pollTimer) })
watch(() => route.query.task, (taskId) => {
  if (typeof taskId === 'string' && taskId !== currentTask.value?.task_id) void selectTask(taskId)
})
</script>

<template>
  <main class="research-page pa-page">
    <section class="hero-panel">
      <div class="hero-copy">
        <div class="eyebrow"><Sparkles :size="14" /> 深度研究</div>
        <h1>今天想研究什么？</h1>
        <p>确认研究方向后，Agent 会调用适合问题的公开检索工具，并整理成带来源链接的报告。</p>
      </div>
      <div class="model-card">
        <div class="model-orb"><BrainCircuit :size="25" /></div>
        <div><small>研究模型</small><strong>DeepSeek</strong></div>
        <span class="online-dot">在线</span>
      </div>

      <div class="composer">
        <div v-if="parentTaskId" class="continuation-label">接续任务 {{ parentTaskId }} <button type="button" @click="parentTaskId = ''">取消关联</button></div>
        <el-input
          v-model="goal"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 6 }"
          resize="none"
          maxlength="4000"
          placeholder="例如：梳理时间序列预测的代表性技术路线，按方法分类并附来源链接。"
          @keydown.ctrl.enter="handleCreate()"
        />
        <div class="composer-footer">
          <span>Ctrl + Enter 发送</span>
          <el-button
            class="research-button"
            :disabled="!canCreate"
            :loading="creating"
            @click="handleCreate()"
          >
            生成计划 <ArrowUpRight v-if="!creating" :size="17" />
          </el-button>
        </div>
      </div>

      <div class="quick-prompts">
        <span>试试这些方向</span>
        <button v-for="item in quickGoals" :key="item" type="button" @click="goal = item">
          {{ item }}
        </button>
      </div>
    </section>

    <section class="stats-grid">
      <el-popover trigger="click" placement="bottom" :width="370"><template #reference><button class="stat-card"><FlaskConical /><div><strong>{{ tasks.length }}</strong><span>全部研究任务</span></div></button></template><div class="stat-menu"><button v-for="task in tasks" :key="task.task_id" @click="focusTask(task.task_id)">{{ task.goal }} · {{ statusLabel(task.status) }}</button><p v-if="!tasks.length">暂无任务</p></div></el-popover>
      <el-popover trigger="click" placement="bottom" :width="370"><template #reference><button class="stat-card success"><CheckCircle2 /><div><strong>{{ successfulTasks }}</strong><span>成功完成</span></div></button></template><div class="stat-menu"><button v-for="task in tasks.filter(item => item.status === 'SUCCESS')" :key="task.task_id" @click="focusTask(task.task_id)">{{ task.goal }}</button><p v-if="!successfulTasks">暂无已完成任务</p></div></el-popover>
      <el-popover trigger="click" placement="bottom" :width="370"><template #reference><button class="stat-card danger"><XCircle /><div><strong>{{ failedTasks.length }}</strong><span>执行失败</span></div></button></template><div class="stat-menu"><div v-for="task in failedTasks" :key="task.task_id" class="stat-task"><button @click="focusTask(task.task_id)">{{ task.goal }}</button><button class="retry-link" @click="retryTask(task)">重新执行</button></div><p v-if="!failedTasks.length">暂无失败任务</p></div></el-popover>
      <el-popover trigger="click" placement="bottom" :width="370">
        <template #reference>
          <button class="stat-card violet">
            <BookOpenCheck /><div><strong>{{ mainDeliverables.length }}</strong><span>{{ mainReport ? '主报告' : '当前交付物' }}</span></div>
          </button>
        </template>
        <div class="stat-menu">
          <button v-for="artifact in mainDeliverables" :key="artifact.artifact_id" @click="focusArtifact(artifact.artifact_id)">{{ artifact.title }}</button>
          <p v-if="!mainDeliverables.length">当前任务暂无交付物</p>
        </div>
      </el-popover>
    </section>

    <div class="history-toolbar">
      <div class="history-toolbar-label"><span>历史任务</span><small>{{ tasks.length }} 项</small></div>
      <div class="history-toolbar-actions">
        <button class="history-refresh" type="button" title="刷新历史任务" aria-label="刷新历史任务" @click="loadTasks"><RefreshCw :size="16" /></button>
        <button class="history-toggle" type="button" :aria-expanded="!historyCollapsed" aria-controls="research-history" @click="historyCollapsed = !historyCollapsed"><ChevronRight v-if="historyCollapsed" :size="16" /><ChevronLeft v-else :size="16" />{{ historyCollapsed ? '展开历史' : '收起历史' }}</button>
      </div>
    </div>
    <section class="workspace-grid" :class="{ 'history-collapsed': historyCollapsed }">
      <aside v-show="!historyCollapsed" id="research-history" class="panel history-panel">
        <div class="panel-heading">
          <div><span>你的研究轨迹</span><h2>最近任务</h2></div>
        </div>

        <div v-if="!historyCollapsed && tasks.length === 0" class="empty-state compact">
          <div class="empty-icon"><FileSearch :size="26" /></div>
          <strong>还没有研究记录</strong><span>从上方输入一个研究目标开始</span>
        </div>
        <button
          v-for="task in historyCollapsed ? [] : tasks"
          :key="task.task_id"
          type="button"
          class="task-card"
          :class="{ active: currentTask?.task_id === task.task_id }"
          @click="selectTask(task.task_id)"
        >
          <span class="task-status" :class="task.status.toLowerCase()" />
          <div class="task-copy">
            <strong>{{ task.goal }}</strong>
            <span><Clock3 :size="12" /> {{ formatTime(task.created_at) }} · {{ task.task_id }}</span>
          </div>
          <el-tag :type="statusType(task.status)" size="small" effect="light">{{ statusLabel(task.status) }}</el-tag>
        </button>
      </aside>

      <section id="research-detail" class="panel detail-panel" v-loading="loadingDetail">
        <div v-if="!currentTask" class="empty-state">
          <div class="empty-icon large"><BrainCircuit :size="34" /></div>
          <strong>选择一个研究任务</strong><span>执行步骤与研究交付物会显示在这里</span>
        </div>
        <template v-else>
          <div class="detail-header">
            <div>
              <span class="detail-kicker">TASK {{ currentTask.task_id }}</span>
              <h2>{{ currentTask.goal }}</h2>
            </div>
            <div class="detail-actions">
              <span v-if="isActive(currentTask.status)" class="elapsed-time"><Clock3 :size="15" /> 已研究 {{ elapsedTime(currentTask.created_at) }}</span>
              <button v-if="reviewKey" type="button" @click="reviewOpen = true">打开计划审阅</button>
              <button v-if="currentTask.guided && (isActive(currentTask.status) || needsReview(currentTask.status) || currentTask.status === 'WAITING_RETRY')" :disabled="reviewBusy" type="button" @click="submitReview({ action: 'cancel' })">停止任务</button>
              <button v-if="currentTask.guided && currentTask.status === 'WAITING_RETRY' && !currentTask.source_unavailable" :disabled="reviewBusy" type="button" @click="submitReview({ action: 'resume' })">继续当前步骤</button>
              <button v-if="currentTask.guided && currentTask.status === 'FAILED' && !currentTask.plan && !currentTask.source_unavailable" :disabled="reviewBusy" type="button" @click="submitReview({ action: 'resume' })">重试规划</button>
              <button v-if="currentTask.status === 'FAILED' && (!currentTask.guided || currentTask.plan)" type="button" @click="retryTask(currentTask)">重新执行</button>
              <button v-if="currentTask.status === 'NO_RESULTS'" type="button" @click="continueFromTask(currentTask)">调整目标后重新检索</button>
              <button v-if="currentTask.status === 'SUCCESS' || currentTask.status === 'PARTIAL'" type="button" @click="continueFromTask(currentTask)">基于结果继续研究</button>
              <button v-if="currentTask.source === 'library' && ['SUCCESS', 'PARTIAL', 'FAILED', 'NO_RESULTS', 'CANCELLED'].includes(currentTask.status)"
                type="button" :disabled="creating" @click="retryTask(currentTask)">改用公开来源</button>
              <el-tag :type="statusType(currentTask.status)" size="large" effect="light">{{ statusLabel(currentTask.status) }}</el-tag>
            </div>
          </div>

          <p v-if="isActive(currentTask.status)" class="research-activity">
            {{ latestEvent ? [latestEvent.title, latestEvent.detail].filter(Boolean).join(' · ') : currentTask.status === 'PENDING' ? '任务已创建，等待执行。' : hasRecentActivity(currentTask.updated_at) ? '研究任务近期有进展，正在继续执行。' : currentTask.plan ? '正在等待当前研究步骤返回；任务会继续运行，不受页面等待时间限制。' : '正在规划研究步骤，复杂任务可能需要较长时间。' }}
          </p>
          <p v-if="currentTask.status === 'WAITING_RETRY'" class="research-activity">{{ latestEvent?.detail }}</p>
          <p v-if="reviewKey" class="research-activity" role="status">任务已暂停，等待你的审阅决定。</p>
          <p v-if="currentTask.source_unavailable" class="research-activity">原论文范围已变化，证据与报告暂不可访问。</p>

          <div class="progress-row">
            <div>
              <span>{{ currentTask.guided ? '已处理节点' : '执行进度' }}</span>
              <strong>{{ completedSteps }} / {{ currentTask.plan?.steps?.length || currentTask.steps.length }} 步</strong>
              <span v-if="currentTask.guided && guidedSteps.length"> · {{ verifiedSteps }} 步{{ currentTask.source === 'discovery' ? '完成整理' : '核验通过' }}</span>
              <span v-if="currentTask.difficulty && currentTask.plan"> · {{ researchDifficultyLabels[currentTask.difficulty] }}档 · 已记录执行 {{ Math.round(currentTask.active_seconds ?? 0) }} 秒</span>
            </div>
            <el-progress :percentage="currentProgress" :stroke-width="9" :show-text="false" />
          </div>

          <div class="section-title artifact-title">
            <span>01</span><div><h3>研究结果</h3><p>{{ mainReport ? '1 份主报告' : `${mainDeliverables.length} 项交付物` }}</p></div>
          </div>
          <div v-if="!mainDeliverables.length" class="empty-artifact">
            {{ currentTask.status === 'NO_RESULTS' ? '本轮没有找到可整理的内容。可回查检索记录，或调整关键词后重试。' : '当前任务尚未生成研究结果' }}
          </div>
          <TransitionGroup name="pa-result" tag="div">
            <div v-for="artifact in mainDeliverables" :id="`artifact-${artifact.artifact_id}`" :key="artifact.artifact_id">
              <ArtifactPanel :artifact="artifact" class="artifact-item" />
            </div>
          </TransitionGroup>
          <details v-if="mainReport && supportingArtifacts.length" :key="`supporting-${currentTask.task_id}`" class="research-history-detail result-details">
            <summary>检索来源与附件（{{ supportingArtifacts.length }}）</summary>
            <div v-for="artifact in supportingArtifacts" :id="`artifact-${artifact.artifact_id}`" :key="artifact.artifact_id">
              <ArtifactPanel :artifact="artifact" class="artifact-item" />
            </div>
          </details>
          <ResearchFeedback v-if="currentTask.guided && currentTask.plan_version &&
            (currentTask.status === 'FAILED' || (['SUCCESS', 'PARTIAL', 'CANCELLED'].includes(currentTask.status) && currentTask.artifacts.length))"
            :key="`${currentTask.task_id}:${currentTask.plan_version}`" :task-id="currentTask.task_id"
            :version="currentTask.plan_version" :feedback="currentTask.feedback" />
          <div class="section-title trace-title"><span>02</span><div><h3>执行轨迹</h3><p>查看智能体的规划与运行状态</p></div></div>
          <div class="timeline">
            <div v-for="(step, index) in displaySteps" :key="step.step_id" class="timeline-item">
              <div class="timeline-marker" :class="step.guided?.quality === 'NEED_MORE_EVIDENCE' && step.status !== 'FAILED' ? 'gap' : step.status.toLowerCase()">
                <CheckCircle2 v-if="step.guided ? step.guided.quality === 'VERIFIED' : step.status === 'SUCCESS'" :size="17" />
                <XCircle v-else-if="step.status === 'FAILED'" :size="17" />
                <AlertCircle v-else-if="step.guided?.quality === 'NEED_MORE_EVIDENCE'" :size="17" />
                <span v-else>{{ index + 1 }}</span>
              </div>
              <div class="step-card">
                <div class="step-header">
                  <div class="step-heading">
                    <div class="step-main"><strong>{{ step.title || step.skill_name }}</strong><code v-if="step.skill_name">{{ step.skill_name }}</code></div>
                    <div class="step-meta">
                      <el-tag :type="step.guided && step.status === 'SUCCESS' ? 'info' : statusType(step.status)" size="small">
                        {{ step.guided && step.status === 'SUCCESS' ? '已执行' : statusLabel(step.status) }}
                      </el-tag>
                      <span v-if="step.duration_ms != null">{{ (step.duration_ms / 1000).toFixed(2) }} 秒</span>
                      <span v-if="step.guided?.quality === 'VERIFIED'">{{ currentTask.source === 'discovery' ? '整理完成' : '核验通过' }}</span>
                      <span v-if="step.guided?.quality === 'NEED_MORE_EVIDENCE' && step.status !== 'FAILED'">{{ currentTask.source === 'discovery' ? '本轮未找到可整理内容' : '存在证据缺口' }}</span>
                      <span v-if="step.guided?.reviewed">{{ step.guided.review_mode === 'automatic' ? '超时继续' : step.guided.review_mode === 'checkpoint_skipped' ? '已完成并继续' : '已审阅' }}</span>
                    </div>
                  </div>
                  <button
                    v-if="step.guided || step.error"
                    type="button"
                    class="step-detail-toggle"
                    :aria-label="`${expandedSteps.has(step.step_id) ? '收起' : '展开'}详情 · ${step.title || step.skill_name}`"
                    :aria-expanded="expandedSteps.has(step.step_id)"
                    :aria-controls="`step-details-${index}`"
                    @click="toggleStepDetails(step.step_id)"
                  >
                    {{ expandedSteps.has(step.step_id) ? '收起详情' : '展开详情' }}
                    <ChevronDown :size="15" aria-hidden="true" />
                  </button>
                </div>
                <div v-if="step.guided || step.error" v-show="expandedSteps.has(step.step_id)" :id="`step-details-${index}`" class="step-details">
                  <p v-if="step.error" class="step-error">{{ step.error }}</p>
                  <template v-if="step.guided">
                    <p class="step-query">检索查询 · {{ step.guided.query }}</p>
                    <p v-if="step.guided.search_scope && currentTask.source === 'discovery'" class="step-query">检索渠道 · {{ researchSearchScopeLabels[step.guided.search_scope] }}</p>
                    <el-button v-if="step.guided.attempts.length && !currentTask.source_unavailable && currentTask.status !== 'AWAITING_APPROVAL'"
                      size="small" @click="openRewind(step.step_id)">从 STEP {{ index + 1 }} 重新规划</el-button>
                    <p v-if="step.guided.reason">{{ step.guided.reason }}</p>
                    <p v-if="step.guided.source_warning && step.guided.source_warning !== step.guided.reason">{{ step.guided.source_warning }}</p>
                    <p v-if="step.guided.missing_criteria?.length">{{ currentTask.source === 'discovery' ? '本轮未覆盖' : '尚未回答' }} · {{ step.guided.missing_criteria.join('、') }}</p>
                    <ResearchFindings :findings="step.guided.findings" />
                    <details v-if="step.guided.attempts.length">
                      <summary>{{ currentTask.source === 'discovery' ? '检索记录' : '检索和核验记录' }}（{{ step.guided.attempts.length }} 次）</summary>
                      <ol>
                        <li v-for="(attempt, attemptIndex) in step.guided.attempts" :key="attemptIndex">
                          v{{ attempt.plan_version }} · {{ attempt.query }} · {{ attempt.reason }}
                          <span v-if="attempt.duration_seconds != null"> · {{ Math.round(attempt.duration_seconds) }} 秒</span>
                          <span v-if="currentTask.source === 'library'"> · 检索 {{ attempt.retrieved }} 个片段，排除 {{ attempt.rejected }} 条候选结论</span>
                          <span v-else-if="attempt.retrieved"> · 整理 {{ attempt.retrieved }} 条搜索结果</span>
                          <ResearchFindings :findings="attempt.findings" />
                        </li>
                      </ol>
                    </details>
                  </template>
                </div>
              </div>
            </div>
          </div>
          <details v-if="currentTask.plan_history?.length" class="research-history-detail">
            <summary>计划版本（当前 v{{ currentTask.plan_version }}）</summary>
            <div v-for="version in currentTask.plan_history" :key="version.version">
              <strong>v{{ version.version }} · {{ version.reason }}</strong>
              <p v-if="version.objective">{{ version.objective }}</p>
              <ol>
                <li v-for="step in version.steps" :key="step.step_id">
                  {{ step.title }} · {{ step.query }}
                  <p v-if="step.criteria?.length">{{ step.criteria.join('、') }}</p>
                </li>
              </ol>
            </div>
          </details>
          <details v-if="currentTask.archived_runs?.length" class="research-history-detail">
            <summary>回退前的执行记录（{{ currentTask.archived_runs.length }}）</summary>
            <details v-for="(run, index) in currentTask.archived_runs" :key="index">
              <summary>计划 v{{ run.plan_version }} · 从 STEP {{ run.from_step }} 回退<template v-if="run.difficulty"> · {{ researchDifficultyLabels[run.difficulty] }}档</template></summary>
              <details v-for="(step, stepIndex) in run.steps" :key="step.step_id">
                <summary>STEP {{ run.from_step + stepIndex }} · {{ step.title }} · {{ statusLabel(step.status) }}</summary>
                <p>{{ step.reason }}</p>
                <ResearchFindings :findings="step.findings" />
                <ul><li v-for="(attempt, attemptIndex) in step.attempts" :key="attemptIndex">{{ attempt.query }} · {{ attempt.reason }}</li></ul>
              </details>
            </details>
          </details>
          <details v-if="keyTaskEvents.length" class="research-history-detail">
            <summary>关键任务事件（{{ keyTaskEvents.length }}）</summary>
            <ol>
              <li v-for="item in keyTaskEvents" :key="item.id">
                {{ formatTime(item.at) }} · v{{ item.plan_version }} ·
                <template v-if="item.step_id"><strong>{{ eventStepLabel(item.plan_version, item.step_id) }}</strong> · </template>
                <strong>{{ item.title }}</strong>
                <span v-if="item.detail"> · {{ item.detail }}</span>
              </li>
            </ol>
          </details>
          <el-dialog v-if="reviewKey" v-model="reviewOpen" :title="currentTask.review_step_id ? '审阅研究节点' : '确认研究计划'"
            align-center append-to-body width="min(720px, 94vw)" :close-on-click-modal="false" destroy-on-close>
            <p v-if="reviewSeconds !== null" class="review-countdown">
              {{ reviewSeconds > 0 ? `剩余 ${reviewSeconds} 秒。未提交调整时按原计划继续。` : '审阅时间已到，正在按原计划继续。' }}
            </p>
            <p v-if="!currentTask.review_step_id && currentTask.preference" class="review-countdown">本次应用你的输出偏好 · {{ researchPreferences[currentTask.preference] }}</p>
            <ResearchReviewDialog :key="reviewKey" :version="currentTask.plan_version || 1" :steps="guidedSteps"
              :current-id="currentTask.review_step_id" :documents="currentTask.documents" :source="currentTask.source"
              :web-search-configured="currentTask.web_search_configured"
              :difficulty="currentTask.difficulty" :assessment="currentTask.assessment" :budgets="currentTask.budgets"
              :objective="currentTask.objective"
              :review-policy="currentTask.review_policy" :busy="reviewBusy || reviewSeconds === 0" @submit="submitReview" />
          </el-dialog>
          <el-dialog v-model="rewindOpen" title="回退并重新规划" align-center append-to-body width="min(640px, 94vw)" destroy-on-close>
            <p>将从 STEP {{ rewindIndex + 1 }} 重新执行。此前的步骤继续沿用，回退前的记录可在历史中查看。</p>
            <el-radio-group v-model="rewindDifficulty" aria-label="重跑难度">
              <el-radio-button v-for="(label, level) in researchDifficultyLabels" :key="level" :value="level">{{ label }}</el-radio-button>
            </el-radio-group>
            <ol class="rewind-questions">
              <li v-for="(question, index) in rewindQuestions" :key="index">
                <strong>STEP {{ rewindIndex + index + 1 }}</strong>
                <el-input v-model="question.title" maxlength="240" :aria-label="`STEP ${rewindIndex + index + 1} 研究问题`" placeholder="研究问题" />
                <el-input v-model="question.query" maxlength="300" :aria-label="`STEP ${rewindIndex + index + 1} 检索查询`" placeholder="检索查询" />
                <el-select v-if="currentTask.source === 'discovery'" v-model="question.search_scope" aria-label="检索渠道" placeholder="按问题选择">
                  <el-option v-for="(label, scope) in researchSearchScopeLabels" :key="scope" :label="label" :value="scope" />
                </el-select>
                <el-input type="textarea" :rows="2" maxlength="1000" :model-value="question.criteria?.join('\n') ?? ''"
                  :aria-label="`STEP ${rewindIndex + index + 1} 验收要求`" placeholder="验收要求（每行一项，最多 5 项）"
                  @update:model-value="value => { question.criteria = value.split('\n') }" />
                <el-button size="small" :disabled="reviewBusy || rewindQuestions.length <= 1" @click="rewindQuestions.splice(index, 1)">移除</el-button>
              </li>
            </ol>
            <el-button :disabled="reviewBusy || rewindQuestions.length >= 30" @click="rewindQuestions.push({ title: '', query: '' })">添加节点</el-button>
            <template #footer>
              <el-button @click="rewindOpen = false">取消</el-button>
              <el-button type="primary" :loading="reviewBusy"
                :disabled="!rewindQuestions.every(validResearchQuestion)"
                @click="submitReview({ action: 'rewind', step_id: rewindStepId, questions: rewindQuestions.map(question => ({
                  ...question, criteria: normalizedCriteria(question.criteria),
                })), difficulty: rewindDifficulty })">保存并从此步重做</el-button>
            </template>
          </el-dialog>

        </template>
      </section>
    </section>
  </main>
</template>

<style scoped>
.timeline-marker.gap { color: #a66417; background: #fff3db; }
.review-countdown { margin: 0 0 .75rem; padding: .55rem .7rem; border-radius: .45rem; background: #edf4ff; color: #264976; font-variant-numeric: tabular-nums; }
.rewind-questions { display: grid; gap: .6rem; max-height: 48dvh; overflow: auto; list-style: none; margin: .75rem 0; padding: 0; }
.rewind-questions li { display: grid; gap: .4rem; padding: .65rem; border: 1px solid #dbe4f2; border-radius: .5rem; }
.rewind-questions .el-button { justify-self: start; }
.step-query { color: #475569; font-size: .85rem; }
.research-history-detail { margin-block: 1rem; padding: .75rem; border: 1px solid #e2e8f0; border-radius: 8px; overflow-wrap: anywhere; }
.research-history-detail summary, .step-card summary { cursor: pointer; }
.research-history-detail ol { padding-inline-start: 1.5rem; }
.result-details > summary { color: #465169; font-weight: 600; }
.result-details[open] > summary { margin-bottom: .75rem; }
.result-details > div:last-child .artifact-item { margin-bottom: 0; }
.step-header { display: flex; flex-wrap: wrap; align-items: start; justify-content: space-between; gap: .45rem .8rem; }
.step-heading { flex: 1 1 10rem; min-width: 0; overflow-wrap: anywhere; }
.step-heading .step-main, .step-heading .step-meta { flex-wrap: wrap; }
.step-detail-toggle { display: inline-flex; align-items: center; gap: .4rem; min-height: 32px; padding: .25rem .55rem; border: 1px solid #dbe4f2; border-radius: .45rem; background: #fff; color: #315b91; font-size: .8rem; white-space: nowrap; cursor: pointer; }
.step-detail-toggle:hover { background: #edf4ff; }
.step-detail-toggle:focus-visible { outline: 2px solid #3162a4; outline-offset: 2px; }
.step-detail-toggle[aria-expanded="true"] svg { transform: rotate(180deg); }
.step-card .step-details { margin-top: .65rem; padding-top: .65rem; border-top: 1px solid #e1e8f2; overflow-wrap: anywhere; }
.step-details > :first-child { margin-top: 0; }
.research-page { position: relative; width: 100%; height: 100vh; min-height: 0; overflow-x: hidden; overflow-y: auto; padding: 32px; color: #172033; background: linear-gradient(145deg, #f7f9ff 0%, #f8fbff 48%, #f5faff 100%); }
.ambient { position: absolute; border-radius: 999px; filter: blur(10px); pointer-events: none; opacity: .5; }
.ambient-one { width: 340px; height: 340px; right: -90px; top: -130px; background: radial-gradient(circle, #c8d9ff, transparent 70%); }
.ambient-two { width: 300px; height: 300px; left: 16%; top: 300px; background: radial-gradient(circle, #dceeff, transparent 70%); }
.hero-panel, .panel, .stat-card { position: relative; z-index: 1; border: 1px solid rgba(255,255,255,.85); box-shadow: 0 18px 55px rgba(57, 73, 125, .09); }
.hero-panel { overflow: hidden; padding: 34px; border-radius: 28px; background: linear-gradient(115deg, rgba(255,255,255,.96), rgba(245,248,255,.9)); }
.hero-panel::after { content: ''; position: absolute; width: 360px; height: 360px; right: -100px; top: -180px; border-radius: 50%; background: linear-gradient(135deg, rgba(74,111,255,.2), rgba(150,91,255,.14)); }
.hero-copy { position: relative; z-index: 1; }
.eyebrow { display: inline-flex; align-items: center; gap: 7px; margin-bottom: 12px; color: #5da5e8; font-size: 11px; font-weight: 800; letter-spacing: .16em; }
.hero-copy h1 { margin: 0; color: #172033; font-size: clamp(30px, 3vw, 46px); line-height: 1.16; letter-spacing: -.04em; }
.hero-copy h1 span { background: linear-gradient(90deg, #5da5e8, #5da5e8); -webkit-background-clip: text; color: transparent; }
.hero-copy p { margin: 14px 0 0; color: #69758d; font-size: 14px; }
.model-card { position: absolute; z-index: 2; right: 34px; top: 34px; display: flex; align-items: center; gap: 11px; padding: 11px 14px; border: 1px solid #e4e9f7; border-radius: 16px; background: rgba(255,255,255,.82); backdrop-filter: blur(12px); }
.model-orb { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 13px; color: #fff; background: linear-gradient(135deg, #5da5e8, #5da5e8); box-shadow: 0 8px 20px rgba(92,102,224,.28); }
.model-card small, .model-card strong { display: block; }.model-card small { color: #929bb0; font-size: 10px; }.model-card strong { font-size: 14px; }
.online-dot { margin-left: 10px; color: #239a70; font-size: 11px; }.online-dot::before { content: ''; display: inline-block; width: 7px; height: 7px; margin-right: 5px; border-radius: 50%; background: #31c48d; box-shadow: 0 0 0 4px #e1f8ef; }
.composer { position: relative; z-index: 2; margin-top: 28px; padding: 7px; border: 1px solid #dfe5f3; border-radius: 20px; background: #fff; box-shadow: 0 14px 36px rgba(55,73,130,.08); }
.composer :deep(.el-textarea__inner) { padding: 15px 17px 8px; border: 0; box-shadow: none; color: #24304a; font-size: 15px; background: transparent; }
.composer-footer { display: flex; align-items: center; justify-content: space-between; padding: 7px 8px 7px 16px; border-top: 1px solid #f0f2f8; color: #8993a9; font-size: 12px; }.composer-footer > span { display: flex; align-items: center; gap: 6px; }
.research-button { height: 40px; border: 0 !important; border-radius: 12px !important; color: #fff !important; background: linear-gradient(120deg, #5da5e8, #5da5e8) !important; box-shadow: 0 8px 20px rgba(83,104,239,.24); }.research-button :deep(span) { display: flex; align-items: center; gap: 6px; }
.quick-prompts { position: relative; z-index: 2; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 13px; }.quick-prompts > span { color: #99a2b4; font-size: 11px; }.quick-prompts button { max-width: 310px; overflow: hidden; padding: 7px 11px; border: 1px solid #e6e9f3; border-radius: 999px; color: #68738a; background: rgba(255,255,255,.72); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; transition: .2s; }.quick-prompts button:hover { color: #5da5e8; border-color: #bdc8fa; background: #fff; transform: translateY(-1px); }
.stats-grid { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 18px 0; }
.stat-card { display: flex; align-items: center; gap: 13px; min-height: 84px; padding: 18px; border-radius: 18px; color: #5da5e8; background: rgba(255,255,255,.78); }.stat-card > svg { padding: 9px; width: 42px; height: 42px; border-radius: 13px; background: #edf6ff; }.stat-card strong, .stat-card span { display: block; }.stat-card strong { color: #202a40; font-size: 22px; line-height: 1; }.stat-card span { margin-top: 5px; color: #8a94a8; font-size: 11px; }.stat-card.success { color: #1c9c71; }.stat-card.success > svg { background: #e8faf3; }.stat-card.danger { color: #e06a6a; }.stat-card.danger > svg { background: #fff0f0; }.stat-card.violet { color: #5d9fdd; }.stat-card.violet > svg { background: #edf6ff; }
.workspace-grid { position: relative; z-index: 1; display: grid; grid-template-columns: minmax(280px, 34%) minmax(0, 1fr); gap: 18px; align-items: start; }
.panel { border-radius: 22px; background: rgba(255,255,255,.86); backdrop-filter: blur(18px); }.history-panel { padding: 20px; }.detail-panel { min-height: 480px; padding: 24px; }
.panel-heading, .detail-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }.panel-heading span, .detail-kicker { color: #74b0e8; font-size: 9px; font-weight: 800; letter-spacing: .18em; }.panel-heading h2, .detail-header h2 { margin: 2px 0 0; }.panel-heading h2 { font-size: 18px; }.detail-header h2 { max-width: 720px; font-size: 20px; line-height: 1.45; }
.icon-button { display: grid; place-items: center; width: 36px; height: 36px; padding: 0; border: 1px solid #e4e8f2; border-radius: 11px; color: #71809b; background: #fff; transition: .2s; }.icon-button:hover { color: #5da5e8; border-color: #c4cdf6; transform: rotate(20deg); }
.task-card { display: flex; align-items: center; width: 100%; gap: 11px; margin-top: 11px; padding: 13px; border: 1px solid transparent; border-radius: 15px; text-align: left; background: #f8f9fc; transition: .2s; }.task-card:hover { border-color: #dfe4f5; background: #fff; transform: translateY(-1px); }.task-card.active { border-color: #cbd3fa; background: linear-gradient(120deg, #f2f9ff, #f4faff); box-shadow: 0 8px 22px rgba(82,104,239,.08); }.task-status { flex: none; width: 8px; height: 8px; border-radius: 50%; background: #a0a8b8; }.task-status.success { background: #2bb985; box-shadow: 0 0 0 4px #e4f8f0; }.task-status.failed { background: #ec7373; box-shadow: 0 0 0 4px #fff0f0; }.task-copy { flex: 1; min-width: 0; }.task-copy strong { display: block; overflow: hidden; color: #344057; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }.task-copy span { display: flex; align-items: center; gap: 4px; margin-top: 5px; color: #9aa3b5; font-size: 9px; }
.progress-row { margin: 20px 0 25px; padding: 14px 16px; border-radius: 14px; background: #f7f8fc; }.progress-row > div { display: flex; justify-content: space-between; margin-bottom: 8px; color: #8c96aa; font-size: 11px; }.progress-row strong { color: #55627a; }.progress-row :deep(.el-progress-bar__inner) { background: linear-gradient(90deg, #5da5e8, #5da5e8); }
.section-title { display: flex; align-items: center; gap: 11px; margin: 20px 0 12px; }.section-title > span { color: #a9b1c1; font-size: 10px; font-weight: 800; }.section-title h3, .section-title p { margin: 0; }.section-title h3 { font-size: 15px; }.section-title p { margin-top: 2px; color: #9aa3b5; font-size: 10px; }.artifact-title { margin-top: 20px; }.trace-title { margin-top: 30px; }
.timeline { position: relative; }.timeline::before { content: ''; position: absolute; left: 15px; top: 12px; bottom: 12px; width: 1px; background: #e4e8f2; }.timeline-item { position: relative; display: flex; gap: 12px; margin-bottom: 10px; }.timeline-marker { z-index: 1; display: grid; place-items: center; flex: none; width: 31px; height: 31px; border: 3px solid #fff; border-radius: 50%; color: #6f7b93; background: #e9ecf3; font-size: 10px; }.timeline-marker.success { color: #1f9b70; background: #dff6ed; }.timeline-marker.failed { color: #d85959; background: #ffe9e9; }.step-card { flex: 1; padding: 12px 14px; border: 1px solid #edf0f5; border-radius: 13px; background: #fff; }.step-main, .step-meta { display: flex; align-items: center; gap: 8px; }.step-main strong { color: #364159; font-size: 12px; }.step-main code { padding: 2px 6px; border-radius: 5px; color: #6ea5d8; background: #f0f8ff; font-size: 9px; }.step-meta { margin-top: 7px; color: #9aa3b5; font-size: 10px; }.step-error { margin: 9px 0 0; padding: 8px 10px; border-radius: 8px; color: #b74e4e; background: #fff4f4; font-size: 10px; line-height: 1.5; }
.empty-state { display: grid; place-items: center; min-height: 380px; text-align: center; }.empty-state.compact { min-height: 240px; }.empty-icon { display: grid; place-items: center; width: 52px; height: 52px; margin-bottom: 10px; border-radius: 17px; color: #5da5e8; background: linear-gradient(135deg, #eef1ff, #edf6ff); }.empty-icon.large { width: 66px; height: 66px; border-radius: 22px; }.empty-state strong, .empty-state span { display: block; }.empty-state strong { color: #4e5970; font-size: 13px; }.empty-state span { margin-top: -105px; color: #a1a9b9; font-size: 11px; }.empty-state.compact span { margin-top: -55px; }.empty-artifact { padding: 26px; border: 1px dashed #dfe4ee; border-radius: 13px; color: #9ca5b7; text-align: center; font-size: 11px; }.artifact-item { margin-bottom: 12px; }
@media (max-width: 1050px) { .model-card { position: relative; right: auto; top: auto; width: max-content; margin-top: 18px; }.stats-grid { grid-template-columns: repeat(2, 1fr); }.workspace-grid { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .research-page { padding: 14px; }.hero-panel { padding: 22px 18px; border-radius: 20px; }.hero-copy h1 { font-size: 29px; }.composer-footer { align-items: flex-start; gap: 10px; flex-direction: column; }.research-button { width: 100%; }.stats-grid { grid-template-columns: 1fr 1fr; gap: 9px; }.stat-card { min-height: 72px; padding: 12px; }.quick-prompts button { max-width: 100%; }.detail-header { align-items: flex-start; flex-direction: column; } }

/* 简约视觉：保留 PaperAgent 紫色识别，降低渐变、阴影与装饰噪音。 */
.research-page { padding: 38px 40px 64px; color: #202123; background: #fff; }
.hero-panel { max-width: 980px; margin: 0 auto; padding: 42px 0 28px; overflow: visible; border: 0; border-radius: 0; background: transparent; box-shadow: none; }
.hero-panel::after { display: none; }
.hero-copy { text-align: center; }
.eyebrow { margin-bottom: 14px; color: #5b97d0; font-size: 12px; font-weight: 600; letter-spacing: 0; }
.hero-copy h1 { color: #202123; font-size: clamp(30px, 3vw, 42px); font-weight: 600; line-height: 1.2; letter-spacing: -.035em; }
.hero-copy p { margin-top: 12px; color: #6b6c70; font-size: 14px; }
.model-card { right: 0; top: 0; gap: 8px; padding: 7px 10px; border-color: #e5e5e5; border-radius: 10px; background: #fff; backdrop-filter: none; }
.model-orb { width: 28px; height: 28px; border-radius: 8px; color: #5b97d0; background: #eff5fb; box-shadow: none; }.model-orb svg { width: 16px; }
.model-card small { color: #8b8d8f; font-size: 9px; }.model-card strong { font-size: 11px; }
.online-dot { margin-left: 4px; color: #6b6c70; font-size: 9px; }.online-dot::before { width: 6px; height: 6px; margin-right: 4px; background: #20a779; box-shadow: none; }
.composer { margin-top: 30px; padding: 8px; border-color: #d9d9dc; border-radius: 20px; box-shadow: 0 4px 18px rgba(0,0,0,.06); transition: border-color .2s, box-shadow .2s; }.composer:focus-within { border-color: #b2c5d7; box-shadow: 0 5px 20px rgba(0,0,0,.08); }
.composer :deep(.el-textarea__inner) { padding: 14px 16px 10px; color: #252626; font-size: 15px; line-height: 1.6; }
.composer-footer { padding: 6px 7px 3px 15px; border-top: 0; color: #9b9d9f; font-size: 11px; }
.research-button { height: 38px; border-radius: 12px !important; background: #5b97d0 !important; box-shadow: none; }.research-button:hover { background: #4b88c2 !important; }
.quick-prompts { justify-content: center; margin-top: 14px; }.quick-prompts > span { color: #a0a2a4; }.quick-prompts button { max-width: 285px; padding: 7px 11px; border-color: #e5e5e7; border-radius: 9px; color: #5f6064; background: #fff; }.quick-prompts button:hover { color: #24304a; border-color: #cbd4dc; background: #f7f7f8; transform: none; }
.stats-grid { max-width: 1200px; grid-template-columns: repeat(4,1fr); gap: 0; margin: 10px auto 18px; border: 1px solid #e8e8ea; border-radius: 14px; background: #fafafa; }
.stat-card { min-height: 68px; padding: 14px 18px; border: 0; border-radius: 0; color: #686b6d !important; background: transparent; box-shadow: none; }.stat-card + .stat-card { border-left: 1px solid #e8e8ea; }.stat-card > svg,.stat-card.success > svg,.stat-card.danger > svg,.stat-card.violet > svg { width: 18px; height: 18px; padding: 0; border-radius: 0; color: #777a7c; background: transparent; }.stat-card strong { color: #27292a; font-size: 18px; }.stat-card span { color: #8c8f91; font-size: 10px; }
.workspace-grid { max-width: 1200px; grid-template-columns: minmax(270px,31%) minmax(0,1fr); gap: 18px; margin: 0 auto; }
.panel { border: 1px solid #e6e6e8; border-radius: 14px; background: #fff; backdrop-filter: none; box-shadow: none; }.history-panel { padding: 16px; }.detail-panel { padding: 22px; }
.panel-heading span,.detail-kicker { color: #8b8e90; font-size: 10px; font-weight: 500; letter-spacing: 0; }.panel-heading h2 { font-size: 16px; }.detail-header h2 { font-size: 18px; font-weight: 600; }
.icon-button { width: 32px; height: 32px; border: 0; border-radius: 8px; color: #737678; background: transparent; }.icon-button:hover { color: #202123; border: 0; background: #f2f2f3; transform: none; }
.task-card { margin-top: 7px; padding: 11px; border: 0; border-radius: 10px; background: transparent; }.task-card:hover { border: 0; background: #f5f5f6; transform: none; }.task-card.active { border: 0; background: #ececee; box-shadow: none; }.task-status.success,.task-status.failed { box-shadow: none; }.task-copy strong { color: #37393a; font-weight: 500; }
.progress-row { margin: 18px 0 24px; padding: 0; background: transparent; }.progress-row :deep(.el-progress-bar__inner) { background: #5b97d0; }
.section-title > span { color: #a1a4a6; font-weight: 500; }.section-title h3 { font-size: 14px; font-weight: 600; }
.step-card { border-color: #e8e8ea; border-radius: 10px; }.step-main strong { color: #414446; font-weight: 500; }.step-main code { color: #5483af; background: #f0f2f8; }
.empty-icon { border-radius: 50%; color: #5b97d0; background: #f0f2f8; }.empty-icon.large { border-radius: 50%; }
@media (max-width:1050px) { .model-card { margin: 18px auto 0; }.stats-grid { grid-template-columns: repeat(2,1fr); }.stat-card:nth-child(3) { border-left: 0; border-top: 1px solid #e8e8ea; }.stat-card:nth-child(4) { border-top: 1px solid #e8e8ea; }.workspace-grid { grid-template-columns: 1fr; }.detail-panel { grid-row: 1; }.history-panel { grid-row: 2; } }
@media (max-width:680px) { .research-page { padding: 18px 14px 84px; }.hero-panel { padding: 26px 0 18px; }.hero-copy h1 { font-size: 30px; }.composer-footer { align-items: center; flex-direction: row; }.composer-footer > span { display: none; }.research-button { width: auto; margin-left: auto; }.stats-grid { gap: 0; }.stat-card { min-height: 62px; padding: 12px; }.quick-prompts { justify-content: flex-start; } }
.stat-card { width: 100%; text-align: left; cursor: pointer; }
.stat-card:hover { background: #edf4fb; }
.stat-menu { max-height: 320px; overflow-y: auto; }
.stat-menu button { display: block; width: 100%; padding: 8px 4px; border-bottom: 1px solid #ececf0; text-align: left; font-size: 12px; }
.stat-menu button:hover { color: #4b88c2; background: #f6fbff; }
.stat-menu p { color: #8a8e91; font-size: 12px; }
.stat-task { display: flex; align-items: center; }.stat-task .retry-link { flex: none; width: auto; color: #5b97d0; white-space: nowrap; }
.continuation-label { display: flex; align-items: center; gap: 12px; margin: 4px 8px; color: #48749d; font-size: 11px; }.continuation-label button { text-decoration: underline; }
.detail-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }.detail-actions button { padding: 6px 9px; border: 1px solid #c4d9ed; border-radius: 7px; color: #4b88c2; background: #f5faff; font-size: 11px; }.detail-actions button:hover { background: #e6f3ff; }
.elapsed-time { display: inline-flex; align-items: center; gap: 5px; color: #5289bd; font-size: 12px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.research-activity { margin: 12px 0 0; color: #6b6c70; font-size: 12px; }
.workspace-grid.history-collapsed { grid-template-columns: minmax(0,1fr); }
.history-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; max-width: 1200px; margin: 0 auto 12px; padding: 10px 14px; border: 1px solid var(--pa-border); border-radius: 12px; background: var(--pa-surface); }
.history-toolbar-label { display: flex; align-items: center; gap: 8px; min-width: 0; font-size: 13px; font-weight: 600; color: var(--pa-ink); }
.history-toolbar-label small { padding: 2px 7px; border-radius: 6px; background: var(--pa-selected); color: var(--pa-secondary); font-size: 11px; font-weight: 500; white-space: nowrap; }
.history-toolbar-actions { display: flex; align-items: center; gap: 6px; flex: none; }
.history-toolbar-actions button { display: inline-flex; align-items: center; justify-content: center; gap: 5px; height: 34px; border: 1px solid var(--pa-border); border-radius: 8px; background: #fff; color: var(--pa-secondary); font-size: 12px; cursor: pointer; }
.history-refresh { width: 34px; }
.history-toggle { padding: 0 10px; }
.history-toolbar-actions button:focus-visible { outline: 2px solid var(--pa-brand); outline-offset: 2px; }
@media(hover:hover) and (pointer:fine) { .history-toolbar-actions button:hover { color: var(--pa-brand); border-color: var(--pa-control); background: var(--pa-selected); } }
@media(max-width:1050px) { .workspace-grid.history-collapsed { grid-template-columns: 1fr; }.history-collapsed .history-panel { grid-row: 2; } }
</style>
