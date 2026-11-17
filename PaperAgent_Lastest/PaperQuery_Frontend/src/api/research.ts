import api from '@/api/api'

export type ResearchSource = 'library' | 'discovery'
export type ResearchSearchScope = 'auto' | 'academic' | 'web' | 'both'
export const researchSearchScopeLabels: Record<ResearchSearchScope, string> = {
  auto: '按问题选择', academic: '学术索引', web: '公开网页', both: '网页和学术索引',
}
export type ResearchQuestion = { title: string; query: string; criteria?: string[]; search_scope?: ResearchSearchScope }
export const normalizedCriteria = (criteria?: string[]) => (criteria ?? []).map(item => item.trim()).filter(Boolean)
export const validResearchQuestion = (question: ResearchQuestion) => {
  const criteria = normalizedCriteria(question.criteria)
  return Boolean(question.title.trim() && question.query.trim()) &&
    criteria.length <= 5 && criteria.every(item => item.length <= 200)
}
export type ResearchDifficulty = 'quick' | 'standard' | 'deep'
export type ResearchReviewPolicy = 'all' | 'checkpoints'
export type ResearchBudget = { first_output_seconds: number; idle_seconds: number; automatic_repairs: number; effort: 'none' | 'low' | 'high' }
export const researchDifficultyLabels: Record<ResearchDifficulty, string> = { quick: '快速', standard: '标准', deep: '深入' }
export const researchPreferences = { concise: '直接给结论', more_evidence: '多展示原文证据', focus: '更聚焦当前问题' } as const
export type ResearchPreference = keyof typeof researchPreferences
export type ResearchFeedback = {
  rating: 'satisfied' | 'unsatisfied'
  reason: 'answer_quality' | 'missing_evidence' | 'incomplete' | 'off_topic' | 'too_verbose' | null
  note: string
  preference: ResearchPreference | null
}
export type ResearchReview = {
  action: 'continue' | 'revise' | 'repair' | 'cancel' | 'resume' | 'rewind'
  revision: number
  questions?: ResearchQuestion[]
  query?: string
  step_id?: string
  difficulty?: ResearchDifficulty
  review_policy?: ResearchReviewPolicy
  objective?: string
}

export interface ResearchFinding {
  text: string
  references: Array<{
    title: string
    document_id: string
    knowledge_id: string
    page: number | null
    quote: string
    url?: string
  }>
}

export interface GuidedStep extends ResearchQuestion {
  step_id: string
  status: string
  quality: string
  reviewed?: boolean
  review_mode?: 'automatic' | 'checkpoint_skipped'
  reason?: string
  source_warning?: string
  missing_criteria?: string[]
  findings: ResearchFinding[]
  papers?: Array<{ title?: string }>
  attempts: Array<{ query: string; reason: string; plan_version: number; retrieved: number; rejected: number; duration_seconds?: number | null; findings: ResearchFinding[] }>
}

// 只创建持久化任务；研究在后端继续执行，通过查询接口读取进度。
export const createResearchTask = async (
  goal: string,
  mode = 'research',
  documentIds: string[] = [],
  parentTaskId?: string,
  source?: ResearchSource | 'auto',
) => {
  const resp = await api.post(
    '/research/tasks',
    { goal, mode, document_ids: documentIds, parent_task_id: parentTaskId, source },
    {
      timeout: 20000,
    },
  )
  return resp.data
}

export const listResearchDocuments = async (): Promise<Array<{ id: string; title: string }>> => {
  const { data } = await api.get('/research/documents')
  return data.data
}

export const reviewResearchTask = async (taskId: string, review: ResearchReview) => {
  const { data } = await api.post(`/research/tasks/${encodeURIComponent(taskId)}/review`, review)
  return data
}

export const saveResearchFeedback = async (taskId: string, version: number, feedback: ResearchFeedback) => {
  await api.put(`/research/tasks/${encodeURIComponent(taskId)}/feedback`, { ...feedback, plan_version: version })
}

// 任务列表
export const listResearchTasks = async () => {
  const resp = await api.get('/research/tasks')
  return resp.data
}

// 任务详情
export const getResearchTask = async (taskId: string) => {
  const resp = await api.get(`/research/tasks/${encodeURIComponent(taskId)}`)
  return resp.data
}
