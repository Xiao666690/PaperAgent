<script setup lang="ts">
import { Search, FileText, ListChecks, Network, Database, BarChart3, UserRound, ArrowUpRight, ArrowRight, Sparkles, Check, Eye, EyeOff, Pause, Play, LoaderCircle, ShieldCheck } from 'lucide-vue-next'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { ElNotification } from 'element-plus'
import { login, register } from '@/api/auth'
import CosmicBackground from './CosmicBackground.vue'
import paperAgentMark from '@/assets/img/paperagent-mark.png'

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const registering = ref(false)
const teamName = ref('') // 注册时填团队名 = 提交加入申请（待管理员审批）
const busy = ref(false)
const showPassword = ref(false)
const motionPaused = ref(false)
const formFocused = ref(false)
const router = useRouter()

const url = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001'

// 向后端发送登录请求并将用户信息存储到 Vuex 和 localStorage 中
const Login = async () => {
  if (busy.value) return
  if (registering.value && password.value !== confirmPassword.value) {
    ElNotification.error({ title: '注册失败', message: '两次输入的密码不一致' })
    return
  }
  busy.value = true
  const user = {
    username: username.value,
    password: password.value,
  }

  try {
    if (registering.value) {
      const res = await register(url, {
        username: username.value,
        password: password.value,
        teamName: teamName.value,
      })
      registering.value = false
      confirmPassword.value = ''
      ElNotification.success({ title: '注册成功', message: res?.msg || '请使用新账户登录' })
      return
    }
    await login(url, user)
    ElNotification({
      title: '登录成功',
      type: 'success',
    })
    router.push('/home')
  } catch (error) {
    if (error instanceof Error) {
      ElNotification({
        title: registering.value ? '注册失败' : '登录失败',
        type: 'error',
        message: error.message,
        })
      console.error('登录失败:', error)
    } else {
      // 处理非 Error 对象的情况
      ElNotification({
        title: registering.value ? '注册失败' : '登录失败',
        type: 'error',
        message: '发生未知错误',
        })
    }
  } finally { busy.value = false }
}
</script>

<template>
  <main class="discovery-login cosmic-login" :class="{ 'motion-paused': motionPaused }">
    <button type="button" class="mobile-motion-toggle" :aria-label="motionPaused ? '播放背景动画' : '暂停背景动画'" :aria-pressed="motionPaused" @click="motionPaused = !motionPaused"><Play v-if="motionPaused" :size="14" /><Pause v-else :size="14" /></button>
    <CosmicBackground :paused="motionPaused || formFocused" />
    <div class="research-orbit-icons" aria-hidden="true"><span class="orbit-science orbit-network"><Network :size="28" :stroke-width="1.4" /></span><span class="orbit-science orbit-database"><Database :size="27" :stroke-width="1.4" /></span><span class="orbit-science orbit-paper"><FileText :size="28" :stroke-width="1.4" /></span><span class="orbit-science orbit-chart"><BarChart3 :size="27" :stroke-width="1.4" /></span></div>
    <div class="discovery-layout">
      <section class="discovery-cover" aria-labelledby="cover-title">
        <div class="cover-brand"><span class="cover-mark"><img :src="paperAgentMark" alt="" /></span><span>PaperAgent</span><span class="brand-edition">RESEARCH WORKSPACE</span></div>
        <div class="cover-story"><span class="cover-eyebrow"><span /> 为持续探索而生</span><h1 id="cover-title" class="discovery-slogan"><span class="slogan-text">让论文向发现更进一步</span><span class="slogan-aura" aria-hidden="true">让论文向发现更进一步</span><span class="slogan-light" aria-hidden="true" /></h1><p>让资料成为证据，让想法成为研究。<br />你的论文、问题与成果，在这里持续连接。</p></div>
        <div class="research-scene" aria-hidden="true">
          <div class="scene-grid" /><div class="scene-halo" />
          <svg class="scene-connectors" viewBox="0 0 640 300" fill="none"><path d="M140 160 C215 160 200 117 295 117 S380 190 490 190" stroke="#d3caf6" stroke-width="1.5" /><path d="M140 180 C220 250 345 260 490 210" stroke="#ddd7f3" stroke-width="1" stroke-dasharray="4 6" /></svg>
          <span class="connection-particle particle-one" /><span class="connection-particle particle-two" /><span class="connection-particle particle-three" />
          <div class="scene-paper scene-float-one"><span class="paper-back paper-back-one" /><span class="paper-back paper-back-two" /><div class="paper-front"><span class="paper-kicker"><FileText :size="14" /> RESEARCH SOURCE</span><strong>每一个问题，<br />始于一份资料。</strong><span class="paper-line long" /><span class="paper-line" /><span class="paper-line short" /><div class="paper-highlight"><span /><span /></div><span class="paper-foot">PDF · 论文与研究资料</span></div><span class="scene-label">01 / 研究资料</span></div>
          <div class="scene-evidence scene-float-two"><div class="evidence-symbol"><Search :size="27" :stroke-width="1.5" /><span class="evidence-ring" /></div><div class="evidence-chip"><Check :size="13" /> 让回答有据可循</div><span class="scene-label">02 / 证据智能</span></div>
          <div class="scene-result scene-float-three"><span class="result-kicker"><Sparkles :size="14" /> NEXT DISCOVERY</span><strong>研究，在此推进。</strong><div class="result-step"><span><Check :size="11" /></span><i class="result-line" /></div><div class="result-step"><span><Check :size="11" /></span><i class="result-line short" /></div><div class="result-step"><span class="result-current" /><i class="result-line" /></div><div class="result-bottom"><span>连接下一轮研究</span><ArrowUpRight :size="16" /></div><span class="scene-label">03 / 受控科研执行</span></div>
          <span class="scene-spark spark-one">+</span><span class="scene-spark spark-two">+</span><span class="scene-caption">SOURCE → EVIDENCE → DISCOVERY</span>
        </div>
        <div class="cover-bottom"><div class="cover-capabilities"><span><ShieldCheck :size="15" /> 证据可追溯</span><span><ListChecks :size="15" /> 执行有边界</span><span><Sparkles :size="15" /> 上下文持续连接</span></div><button type="button" class="motion-toggle" :aria-pressed="motionPaused" :aria-label="motionPaused ? '播放封面动画' : '暂停封面动画'" @click="motionPaused = !motionPaused"><Play v-if="motionPaused" :size="14" /><Pause v-else :size="14" /></button></div>
      </section>
      <section class="discovery-form-panel" aria-label="账户登录与注册" @focusin="formFocused = true" @focusout="formFocused = !!($event.relatedTarget && $event.currentTarget && ($event.currentTarget as HTMLElement).contains($event.relatedTarget as Node))">
        <div class="auth-card">
          <div class="auth-heading"><span class="auth-eyebrow"><UserRound :size="15" />{{ registering ? '创建账户' : '账户登录' }}</span><h2>{{ registering ? '创建 PaperAgent 账户' : '登录 PaperAgent' }}</h2><p>{{ registering ? '创建账户，让每一次探索留下成果。' : '继续上一次思考，开启下一次发现。' }}</p></div>
          <form @submit.prevent="Login">
            <div class="auth-fields"><div class="auth-field"><Label for="username">用户名</Label><Input id="username" v-model="username" placeholder="请输入用户名" autocomplete="username" required :disabled="busy" /></div>
              <div class="auth-field"><Label for="password">密码</Label><div class="password-wrap"><Input id="password" v-model="password" :type="showPassword ? 'text' : 'password'" placeholder="请输入密码" :autocomplete="registering ? 'new-password' : 'current-password'" :minlength="registering ? 8 : undefined" required :disabled="busy" /><button type="button" class="password-toggle" :aria-label="showPassword ? '隐藏密码' : '显示密码'" :aria-pressed="showPassword" @click="showPassword = !showPassword"><EyeOff v-if="showPassword" :size="18" /><Eye v-else :size="18" /></button></div></div>
              <div v-if="registering" class="auth-field"><Label for="confirm-password">确认密码</Label><Input id="confirm-password" v-model="confirmPassword" type="password" autocomplete="new-password" placeholder="再次输入密码" required :disabled="busy" /></div>
              <div v-if="registering" class="auth-field"><Label for="team-name">团队名 <span class="field-optional">（可选）</span></Label><Input id="team-name" v-model="teamName" placeholder="填写团队管理员名字" autocomplete="off" :disabled="busy" /><p class="auth-field-hint">管理员批准后即可加入团队工作空间。</p></div>
            </div>
            <Button type="submit" class="discovery-submit" :disabled="busy" :aria-busy="busy"><LoaderCircle v-if="busy" class="auth-spinner" :size="18" /><span>{{ busy ? '正在连接…' : registering ? '创建账户' : '进入研究空间' }}</span><ArrowRight v-if="!busy" :size="18" /></Button>
            <div class="auth-divider"><span /> <i>{{ registering ? '已经有自己的空间？' : '第一次使用 PaperAgent？' }}</i><span /></div>
            <button type="button" class="discovery-auth-switch" :disabled="busy" @click="registering = !registering; confirmPassword = ''; showPassword = false">{{ registering ? '返回登录' : '创建一个账户' }}<ArrowUpRight :size="15" /></button>
            <p v-if="!registering" class="auth-demo">本地体验账号：admin / 123456</p>
          </form>
        </div>
        <p class="auth-footnote"><span class="auth-footnote-mark" /> 从论文到发现 · 在同一个研究空间里</p>
      </section>
    </div>
  </main>
</template>
