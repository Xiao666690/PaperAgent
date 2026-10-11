import { h } from 'vue'
import type { Router } from 'vue-router'
import { ElNotification } from 'element-plus'
import { listResearchTasks } from '@/api/research'

const statuses = new Map<string, string>()
let appRouter: Router | undefined
let accountToken = ''
let polling = false
const active = (status?: string) => status === 'PENDING' || status === 'RUNNING'

export function trackResearchTask(task: { task_id: string; status?: string }) {
  const token = localStorage.getItem('token') || ''
  if (token !== accountToken) { statuses.clear(); accountToken = token }
  statuses.set(task.task_id, task.status || 'PENDING')
}

export function notifyTaskCompletion(title: string, text: string, path: string, token: string | null, differentSession = false) {
  if (!appRouter || !token || token !== localStorage.getItem('token')) return
  if (appRouter.currentRoute.value.path === '/login') return
  const targetPath = path.split('?')[0]
  if (!differentSession && document.visibilityState === 'visible' && appRouter.currentRoute.value.path.toLowerCase() === targetPath.toLowerCase()) return
  const toast = ElNotification({
    title, type: 'success', duration: 0,
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
  const poll = async () => {
    const token = localStorage.getItem('token') || ''
    if (token !== accountToken) { statuses.clear(); accountToken = token }
    if (!token || router.currentRoute.value.path === '/login' || polling) return
    polling = true
    try {
      const response = await listResearchTasks()
      if (token !== localStorage.getItem('token')) return
      for (const task of response.data || []) {
        const previous = statuses.get(task.task_id)
        statuses.set(task.task_id, task.status)
        // Seed existing history silently; announce only an observed active -> completed transition.
        if (active(previous) && task.status === 'SUCCESS') {
          notifyTaskCompletion('深度研究已完成', task.goal, `/home/research?task=${encodeURIComponent(task.task_id)}`, token)
        }
      }
    } catch { /* Temporary network failures retry on the next poll without notification spam. */ }
    finally { polling = false }
  }
  const timer = setInterval(poll, 4000)
  const removeRouteHook = router.afterEach(() => { void poll() })
  const onVisible = () => { if (document.visibilityState === 'visible') void poll() }
  document.addEventListener('visibilitychange', onVisible)
  void poll()
  return () => { clearInterval(timer); removeRouteHook(); document.removeEventListener('visibilitychange', onVisible); appRouter = undefined }
}
