import { createRouter, createWebHistory } from 'vue-router'
import progress from '@bassist/progress'
import routes from './routes'
import { clearSession, sessionExpiredEvent } from '@/services/session'

// 配置进度条
progress.configure({ showSpinner: false })
progress.setColor('var(--c-brand)')

// 创建路由器实例
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: (_to, _from, savedPosition) => {
    return savedPosition ? savedPosition : { top: 0, left: 0 }
  },
})

// 导航守卫
router.beforeEach((to, _from, next) => {
  progress.start()

  if (to.meta.requiresAuth) {
    const token = localStorage.getItem('token')
    const expiresAt = Number(localStorage.getItem('tokenExpiresAt'))
    const expired = Boolean(token && expiresAt > 0 && Date.now() >= expiresAt * 1000)
    if (!token || !localStorage.getItem('username') || expired) {
      if (expired) clearSession()
      next({ path: '/login', query: { redirect: to.fullPath, ...(expired ? { reason: 'expired' } : {}) } })
      return
    }
  }

  // 仅 admin 可访问的路由（如团队管理），普通用户跳回首页
  if (to.matched.some((record) => record.meta.role === 'admin')) {
    const role = localStorage.getItem('role')
    if (role !== 'admin') {
      next('/home/dashboard')
      return
    }
  }

  next()
})

window.addEventListener(sessionExpiredEvent, () => {
  const route = router.currentRoute.value
  if (route.meta.requiresAuth) {
    void router.replace({ path: '/login', query: { redirect: route.fullPath, reason: 'expired' } })
  }
})

router.afterEach(() => {
  // const { title } = to.meta
  document.title = `PaperAgent · Academic Research Workspace`
  progress.done()
})

export default router
