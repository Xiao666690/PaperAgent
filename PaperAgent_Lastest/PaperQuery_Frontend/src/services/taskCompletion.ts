import { h } from 'vue'
import type { Router } from 'vue-router'
import { ElNotification } from 'element-plus'
import { listResearchTasks } from '@/api/research'

const statuses = new Map<string, string>()
let appRouter: Router | undefined
let accountToken = ''
let polling = false
const active = (status?: string) => Boolean(status && ['PENDING', 'QUEUED', 'RUNNING', 'AWAITING_APPROVAL', 'AWAITING_INPUT'].includes(status))

export function trackResearchTask(task: { task_id: string; status?: string }) {
  const token = localStorage.getItem('token') || ''
  if (token !== accountToken) { statuses.clear(); accountToken = token }
  statuses.set(task.task_id, task.status || 'PENDING')
}

export function notifyTaskCompletion(title: string, text: string, path: string, token: string | null, differentSession = false, type: 'success' | 'info' = 'success') {
  if (!appRouter || !token || token !== localStorage.getItem('token')) return
  if (appRouter.currentRoute.value.path === '/login') return
  const targetPath = path.split('?')[0]
  if (!differentSession && document.visibilityState === 'visible' && appRouter.currentRoute.value.path.toLowerCase() === targetPath.toLowerCase()) return
  const toast = ElNotification({
    title, type, duration: 0,
    message: h('div', [
      h('p', { style: 'max-width:280px;overflow-wrap:anywhere' }, text.slice(0, 100)),
      h('button', {
        type: 'button', class: 'task-completion-link',
        onClick: () => { toast.close(); appRouter?.push(path) },
      }, '查看结果 →'),
    ]),
  })
}

export function startTaskCompletionMonitor(router: Router) {
  appRouter = router
  const reviewToasts = new Map<string, { updatedAt: string; close: () => void }>()
  const inResearch = () => router.currentRoute.value.name === 'research'
  const clearReviewToasts = () => {
    for (const toast of reviewToasts.values()) toast.close()
    reviewToasts.clear()
  }
  const poll = async () => {
    const token = localStorage.getItem('token') || ''
    if (token !== accountToken) { statuses.clear(); clearReviewToasts(); accountToken = token }
    if (!token || !router.currentRoute.value.meta.requiresAuth || polling) return
    polling = true
    try {
      const response = await listResearchTasks()
      if (token !== localStorage.getItem('token')) return
      for (const task of response.data || []) {
        const previous = statuses.get(task.task_id)
        statuses.set(task.task_id, task.status)
        const existing = reviewToasts.get(task.task_id)
        if (existing && (task.status !== 'AWAITING_INPUT' || existing.updatedAt !== task.updated_at)) {
          existing.close()
          reviewToasts.delete(task.task_id)
        }
        const remaining = Date.parse(task.review_deadline) - Date.now()
        if (task.status === 'AWAITING_INPUT' && remaining > 0 && !inResearch() && !reviewToasts.has(task.task_id)) {
          const path = `/home/research?task=${encodeURIComponent(task.task_id)}`
          const toast = ElNotification({
            title: '研究节点已完成，待审阅',
            type: 'warning',
            position: 'top-right',
            duration: remaining,
            message: h('div', [
              h('p', { style: 'overflow-wrap:anywhere' }, task.goal.slice(0, 100)),
              h('p', `约 ${Math.ceil(remaining / 1000)} 秒后按原计划继续`),
              h('button', {
                type: 'button', class: 'task-completion-link',
                onClick: () => { toast.close(); void router.push(path) },
              }, '去审阅 →'),
            ]),
          })
          reviewToasts.set(task.task_id, { updatedAt: task.updated_at, close: () => toast.close() })
        }
        // Seed existing history silently; announce only an observed active -> completed transition.
        if (active(previous) && ['SUCCESS', 'PARTIAL', 'NO_RESULTS'].includes(task.status)) {
          const empty = task.status === 'NO_RESULTS'
          const title = empty ? '本轮研究暂无结果' : task.status === 'PARTIAL' ? '深度研究已交付部分结果' : '深度研究已完成'
          notifyTaskCompletion(title, task.goal, `/home/research?task=${encodeURIComponent(task.task_id)}`, token, false, empty ? 'info' : 'success')
        }
      }
    } catch { /* Temporary network failures retry on the next poll without notification spam. */ }
    finally { polling = false }
  }
  const timer = setInterval(poll, 4000)
  const removeRouteHook = router.afterEach(() => {
    if (inResearch() || router.currentRoute.value.path === '/login') {
      for (const toast of reviewToasts.values()) toast.close()
    }
    void poll()
  })
  const onVisible = () => { if (document.visibilityState === 'visible') void poll() }
  document.addEventListener('visibilitychange', onVisible)
  void poll()
  return () => { clearInterval(timer); clearReviewToasts(); removeRouteHook(); document.removeEventListener('visibilitychange', onVisible); appRouter = undefined }
}
