<template>
  <div class="paper-chat border">
    <header class="chat-header">
      <div><h1 class="text-lg font-bold">论文问答</h1><p class="text-xs text-gray-500">围绕当前论文提问；支持引用与外部学术检索</p></div>
      <div class="chat-header-actions">
        <button type="button" class="session-button" :disabled="sending" @click="newSession"><Plus :size="14" />新建会话</button>
        <button type="button" class="session-button" @click="historyOpen = true"><History :size="14" />历史会话</button>
      <div ref="modelPicker" class="model-picker">
        <button type="button" class="model-select" aria-label="选择模型" :aria-expanded="modelMenuOpen" aria-haspopup="menu" @click="modelMenuOpen = !modelMenuOpen" @keydown.esc="modelMenuOpen = false">
          {{ modelStore.getModelLabel(selectedModel) }} <span aria-hidden="true">⌄</span>
        </button>
        <div v-if="modelMenuOpen" class="model-menu" role="menu" @keydown.esc="modelMenuOpen = false">
          <button v-for="item in modelStore.modelOptions" :key="item.value" type="button" role="menuitemradio" :aria-checked="selectedModel === item.value" @click="selectedModel = item.value; modelMenuOpen = false">
            {{ item.label }} <span v-if="selectedModel === item.value" aria-hidden="true">✓</span>
          </button>
        </div>
      </div>
      </div>
    </header>
    <el-dialog v-model="historyOpen" title="当前论文的历史会话" width="min(520px, calc(100vw - 32px))" append-to-body>
      <p class="session-history-note">{{ sending ? '当前回答生成中，完成后可以切换会话。' : '选择会话即可继续之前的讨论。记录保存在当前浏览器。' }}</p>
      <div class="session-history-list">
        <div v-for="session in sortedSessions" :key="session.id" class="session-history-item" :class="{ active: session.id === activeSessionId }">
          <form v-if="renamingId === session.id" class="session-rename-form" @submit.prevent="saveSessionTitle" @keydown.esc.stop.prevent="cancelRename">
            <label class="sr-only" :for="`session-title-${session.id}`">会话标题</label>
            <input :id="`session-title-${session.id}`" v-model="renameTitle" maxlength="80" aria-label="会话标题" @input="renameError = ''" />
            <p v-if="renameError" class="rename-error" role="alert">{{ renameError }}</p>
            <div class="rename-actions"><button type="submit">保存</button><button type="button" @click="cancelRename">取消</button></div>
          </form>
          <template v-else>
            <button type="button" class="session-open" :disabled="sending" @click="openSession(session.id)">
              <div><strong>{{ sessionTitle(session) }}</strong><span>{{ formatSessionTime(session.updatedAt) }} · {{ session.messages.filter(item => item.role === 'user').length }} 次提问</span></div>
              <span v-if="session.id === activeSessionId" class="session-current">当前</span><ChevronRight v-else :size="16" />
            </button>
            <button type="button" class="session-rename-button" :aria-label="`重命名会话：${sessionTitle(session)}`" @click="startRename(session)"><Pencil :size="13" />重命名</button>
          </template>
        </div>
        <p v-if="!sessions.length" class="session-history-note">暂无历史会话</p>
      </div>
    </el-dialog>
    <main ref="messageContainer" class="chat-messages">
      <p v-if="!messages.length" class="text-sm text-gray-500">可以询问方法、实验和结论，也可以选中左侧段落后追问。</p>
      <div v-for="(message, index) in messages" :key="index" class="mb-3">
        <MessageBox v-bind="displayMessage(message)" />
      </div>
    </main>
    <div v-if="selectedText" class="selected-quote">
      <span>已选第 {{ selectedPage }} 页：{{ selectedText.slice(0, 140) }}{{ selectedText.length > 140 ? '…' : '' }}</span>
      <button type="button" @click="emit('clear-selection')">×</button>
    </div>
    <form class="chat-composer" @submit.prevent="send">
      <textarea v-model="draft" rows="2" placeholder="询问这篇论文或探索相关研究…" aria-label="论文问题" @keydown.enter="handleEnter" />
      <button type="submit" :disabled="sending || !draft.trim()">{{ sending ? '回答中…' : '发送' }}</button>
    </form>
  </div>
</template>

<style scoped>
.paper-chat { display: flex; flex-direction: column; box-sizing: border-box; contain: inline-size; width: 100%; max-width: 100%; min-width: 0; min-height: 0; height: 100%; overflow: clip; background: white; }
.chat-header { position: relative; z-index: 20; display: flex; justify-content: space-between; align-items: center; gap: 8px; min-width: 0; padding: 10px 14px; border-bottom: 1px solid #e5e7eb; }
.chat-header { flex-wrap: wrap; }.chat-header-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-left: auto; }
.session-button { display: inline-flex; align-items: center; justify-content: center; gap: 4px; padding: 6px 8px; border: 1px solid #dae6f1; border-radius: 7px; color: #487cad; background: #f8fbff; font-size: 12px; white-space: nowrap; }.session-button:disabled { opacity: .5; cursor: not-allowed; }
.session-history-note { margin: 0 0 12px; font-size: 12px; color: #64748b; }.session-history-list { max-height: min(55vh, 440px); overflow-y: auto; overscroll-behavior: contain; padding: 2px; display: grid; gap: 8px; }
.session-history-item { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; padding: 12px; border: 1px solid #e2e8f0; border-radius: 10px; text-align: left; background: #fff; color: #334155; }.session-history-item.active { border-color: #adcfef; background: #edf6ff; }.session-open { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex: 1; min-width: 0; text-align: left; }.session-open > div { min-width: 0; }.session-open:disabled { cursor: not-allowed; opacity: .6; }.session-history-item strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }.session-open div > span { display: block; margin-top: 6px; color: #64748b; font-size: 11px; }.session-current { flex: none; font-size: 11px; color: #147bdf; }.session-history-item:disabled { cursor: not-allowed; }
.session-rename-button { display: inline-flex; align-items: center; gap: 4px; flex: none; padding: 6px; border-radius: 6px; color: #487cad; font-size: 11px; white-space: nowrap; }.session-rename-button:hover { background: #e5f1fc; }
.session-rename-form { width: 100%; min-width: 0; }.session-rename-form input { width: 100%; min-width: 0; border: 1px solid #adcfef; border-radius: 7px; padding: 8px; background: white; font-size: 13px; }.rename-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }.rename-actions button { padding: 5px 10px; border: 1px solid #dae6f1; border-radius: 6px; font-size: 12px; color: #487cad; background: white; }.rename-actions button[type=submit] { background: #147bdf; color: white; border-color: #147bdf; }.rename-error { margin: 6px 0 0; color: #b42318; font-size: 12px; }
.model-picker { position: relative; flex: none; }
.model-select { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-width: 112px; padding: 6px 9px; border: 1px solid #d1d5db; border-radius: 6px; background: #fff; color: #1f2937; font-size: 12px; }
.model-menu { position: absolute; top: calc(100% + 5px); right: 0; z-index: 30; width: 142px; padding: 4px; border: 1px solid #d1d5db; border-radius: 8px; background: #fff; color: #1f2937; box-shadow: 0 8px 24px #1f293726; }
.model-menu button { display: flex; justify-content: space-between; width: 100%; padding: 7px 8px; border-radius: 5px; text-align: left; font-size: 12px; }
.model-menu button:hover, .model-menu button[aria-checked='true'] { background: #eff5fa; color: #487cad; }
.chat-messages { flex: 1; min-width: 0; min-height: 0; max-width: 100%; overflow-x: hidden; overflow-y: auto; padding: 12px; }
.chat-messages > div { min-width: 0; max-width: 100%; }
.selected-quote { display: flex; justify-content: space-between; gap: 6px; min-width: 0; max-width: 100%; padding: 7px 12px; background: #f0f7ff; color: #475569; font-size: 12px; }
.selected-quote span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.selected-quote button { font-size: 18px; }
.chat-composer { display: flex; gap: 8px; padding: 10px; border-top: 1px solid #e5e7eb; }
.chat-composer textarea { flex: 1; min-width: 0; resize: vertical; border: 1px solid #d1d5db; border-radius: 8px; padding: 7px; font-size: 13px; }
.chat-composer button { align-self: end; border-radius: 8px; background: #356fce; color: white; padding: 8px 12px; white-space: nowrap; }
.chat-composer button:disabled { opacity: .5; }
</style>

<script setup lang="ts">
import { Plus, History, ChevronRight, Pencil } from 'lucide-vue-next'
import MessageBox from '@/views/chat/components/MessageBox.vue'
import { askQuestionStream, type CitationItem, type ExternalPaperResult, type SearchProgress } from '@/api/qa'
import { useModelStore, type ModelType } from '@/stores/modelStore'
import { getDocumentSummary } from '@/api/data'

const props = defineProps<{ knowledgeId: string; documentId: string; selectedText: string; selectedPage: number }>()
const emit = defineEmits<{ 'clear-selection': [] }>()
type PaperMessage = {
  role: 'user' | 'gpt' | 'system'; content: string; modelLabel?: string;
  requestContent?: string
  citations?: CitationItem[]; externalPapers?: ExternalPaperResult;
  searchSteps?: string[]; searchState?: SearchProgress['state'];
  status?: 'thinking' | 'streaming' | 'done' | 'error'
  startedAt?: number; thinkingMs?: number; durationMs?: number
}
const modelStore = useModelStore()
const selectedModel = ref<ModelType>(modelStore.currentModel)
const modelMenuOpen = ref(false)
const modelPicker = ref<HTMLElement | null>(null)
const closeModelMenuOutside = (event: PointerEvent) => {
  if (!modelPicker.value?.contains(event.target as Node)) modelMenuOpen.value = false
}
const messages = ref<PaperMessage[]>([])
const displayMessage = (message: PaperMessage) => {
  const { requestContent, ...visible } = message
  return visible
}
const normalizeSavedMessage = (item: PaperMessage): PaperMessage => {
  if (item.role !== 'user' || item.requestContent || typeof item.content !== 'string') return item
  // Compatibility with previously saved questions containing our exact context suffix.
  const legacy = item.content.match(/^([\s\S]+?)\n\n请结合当前论文第 \d+ 页选中的文字：\n“[\s\S]*”$/)
  return legacy ? { ...item, content: legacy[1], requestContent: item.content } : item
}
const draft = ref('')
const sending = ref(false)
const handleEnter = (event: KeyboardEvent) => {
  if (event.isComposing || event.keyCode === 229 || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return
  event.preventDefault()
  send()
}
const messageContainer = ref<HTMLElement | null>(null)
const storageKey = () => `paperquery:paper-chat:${localStorage.getItem('username') || 'guest'}:${props.documentId}`

type PaperSession = { id: string; title?: string; createdAt: number; updatedAt: number; messages: PaperMessage[] }
const sessions = ref<PaperSession[]>([])
const activeSessionId = ref('')
const historyOpen = ref(false)
const sortedSessions = computed(() => [...sessions.value].sort((a, b) => b.updatedAt - a.updatedAt))
const sessionsKey = () => `${storageKey()}:sessions:v1`
const sessionTitle = (session: PaperSession) => session.title || session.messages.find(item => item.role === 'user')?.content.trim().slice(0, 80) || '新会话'
const formatSessionTime = (time: number) => new Date(time).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
const persist = () => {
  const session = sessions.value.find(item => item.id === activeSessionId.value)
  if (session) { session.messages = messages.value; session.updatedAt = Date.now() }
  try { localStorage.setItem(sessionsKey(), JSON.stringify({ activeSessionId: activeSessionId.value, sessions: sessions.value })) }
  catch (error) { console.error('聊天记录保存失败', error) }
}
const renamingId = ref('')
const renameTitle = ref('')
const renameError = ref('')
const cancelRename = () => { renamingId.value = ''; renameError.value = '' }
const startRename = (session: PaperSession) => {
  renamingId.value = session.id
  renameTitle.value = sessionTitle(session)
  renameError.value = ''
  nextTick(() => {
    const input = document.getElementById(`session-title-${session.id}`) as HTMLInputElement | null
    input?.focus(); input?.select()
  })
}
const saveSessionTitle = () => {
  const title = renameTitle.value.trim()
  if (!title) { renameError.value = '请输入会话标题'; return }
  const session = sessions.value.find(item => item.id === renamingId.value)
  if (session) { session.title = title.slice(0, 80); persist() }
  cancelRename()
}
watch(historyOpen, open => { if (!open) cancelRename() })
const newSession = () => {
  if (sending.value) return
  persist()
  const current = sessions.value.find(item => item.id === activeSessionId.value)
  if (current && !current.messages.length) { historyOpen.value = false; return }
  const now = Date.now()
  const session = { id: crypto.randomUUID(), createdAt: now, updatedAt: now, messages: [] }
  sessions.value.unshift(session)
  activeSessionId.value = session.id
  messages.value = []
  draft.value = ''
  historyOpen.value = false
  emit('clear-selection')
  persist()
}
const openSession = (id: string) => {
  if (sending.value) return
  const session = sessions.value.find(item => item.id === id)
  if (!session) return
  persist()
  activeSessionId.value = id
  messages.value = session.messages
  draft.value = ''
  historyOpen.value = false
  emit('clear-selection')
  persist()
  scrollToBottom()
}
const restore = async () => {
  sessions.value = []
  activeSessionId.value = ''
  const restoreKey = sessionsKey()
  const normalize = (items: PaperMessage[]) => items.map(item => ({ ...normalizeSavedMessage(item), status: item.status === 'thinking' || item.status === 'streaming' ? 'error' as const : item.status }))
  try {
    const saved = JSON.parse(localStorage.getItem(restoreKey) || 'null')
    if (saved && Array.isArray(saved.sessions) && saved.sessions.length) {
      sessions.value = saved.sessions.filter((item: PaperSession) => item.id && Array.isArray(item.messages)).map((item: PaperSession) => ({ ...item, messages: normalize(item.messages) }))
      activeSessionId.value = sessions.value.find(item => item.id === saved.activeSessionId)?.id || sessions.value[0]?.id || ''
      messages.value = sessions.value.find(item => item.id === activeSessionId.value)?.messages || []
      if (activeSessionId.value) { persist(); return }
    }
    const legacy = JSON.parse(localStorage.getItem(storageKey()) || '[]')
    if (Array.isArray(legacy) && legacy.length) {
      const now = Date.now()
      const session = { id: crypto.randomUUID(), createdAt: now, updatedAt: now, messages: normalize(legacy) }
      sessions.value = [session]; activeSessionId.value = session.id; messages.value = session.messages
      persist(); return
    }
  } catch (error) { console.error('聊天记录读取失败', error) }
  newSession()
  const initialId = activeSessionId.value
  try {
    const response = await getDocumentSummary(props.knowledgeId, props.documentId)
    const summary = response.data?.summarize
    if (summary && restoreKey === sessionsKey() && initialId === activeSessionId.value && !messages.value.length) {
      messages.value.push({ role: 'gpt', content: summary, modelLabel: '论文摘要', status: 'done' }); persist()
    }
  } catch (error) { console.info('尚无论文摘要', error) }
}

const send = async () => {
  const input = draft.value.trim()
  if (!input || sending.value) return
  const question = props.selectedText
    ? `${input}\n\n请结合当前论文第 ${props.selectedPage} 页选中的文字：\n“${props.selectedText}”`
    : input
  draft.value = ''
  emit('clear-selection')
  const context = messages.value.filter(item => item.role !== 'system' && item.content.trim()).slice(-6)
    .map(item => `${item.role === 'user' ? '用户' : '助手'}: ${(item.requestContent || item.content).slice(0, 800)}`).join('\n')
  messages.value.push({ role: 'user', content: input, ...(question !== input ? { requestContent: question } : {}) })
  const reply = reactive<PaperMessage>({ role: 'gpt', content: '', modelLabel: modelStore.getModelLabel(selectedModel.value), status: 'thinking', startedAt: Date.now() })
  messages.value.push(reply)
  persist()
  sending.value = true
  try {
    await askQuestionStream(question, [props.documentId], selectedModel.value, context,
      text => { if (reply.thinkingMs == null) reply.thinkingMs = Date.now() - (reply.startedAt || Date.now()); reply.content += text; reply.status = 'streaming'; scrollToBottom() },
      citations => { reply.citations = citations },
      progress => {
        reply.searchState = progress.state
        if (progress.text && !reply.searchSteps?.includes(progress.text)) reply.searchSteps = [...(reply.searchSteps || []), progress.text]
        scrollToBottom()
      },
      result => { reply.externalPapers = result; scrollToBottom() },
    )
    reply.status = 'done'
  } catch (error: any) {
    reply.status = 'error'
    reply.content ||= `请求失败：${error?.message || error}`
  } finally { reply.durationMs = Date.now() - (reply.startedAt || Date.now()); sending.value = false; persist(); scrollToBottom() }
}

const scrollToBottom = () => nextTick(() => { if (messageContainer.value) messageContainer.value.scrollTop = messageContainer.value.scrollHeight })
watch(() => props.documentId, () => { messages.value = []; restore() })
onMounted(() => { restore(); document.addEventListener('pointerdown', closeModelMenuOutside) })
onBeforeUnmount(() => document.removeEventListener('pointerdown', closeModelMenuOutside))
</script>
