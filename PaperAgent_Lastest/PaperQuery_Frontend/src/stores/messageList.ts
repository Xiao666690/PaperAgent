import { computed, reactive } from 'vue'
import { defineStore } from 'pinia'
import { updateMemory } from '@/api/chat'
import { askQuestionStream, type CitationItem, type ExternalPaperResult, type SearchProgress } from '@/api/qa'
import { useChatHistoryStore } from './chatHistory'
import type { ChatDocumentSnapshot } from './chatHistory'
import { useDocumentListStore } from './documentList'
import { useMemoryStore } from './memory'
import { useModelStore } from './modelStore'
import { notifyTaskCompletion } from '@/services/taskCompletion'

export type Message = {
  id?: number
  content: string
  role: 'user' | 'gpt' | 'system'
  model?: string
  modelLabel?: string
  createdAt?: number
  thinkingMs?: number
  durationMs?: number
  citations?: CitationItem[]
  externalPapers?: ExternalPaperResult
  searchStatus?: string
  searchState?: SearchProgress['state']
  searchSteps?: string[]
  status?: 'thinking' | 'streaming' | 'done' | 'error'
  documents?: ChatDocumentSnapshot[]
}

export const useMessageListStore = defineStore('messageList', () => {
  const state = reactive({
    messageList: <Array<Message>>[],
  })

  const messages = computed(() => state.messageList)

  function addUserMessage(message: Message) {
    const documentStore = useDocumentListStore()
    const userMessage: Message = {
      ...message,
      documents: documentStore.getSelectedSnapshots(),
      id: state.messageList.length,
      createdAt: Date.now(),
    }
    state.messageList.push(userMessage)
    saveHistorySnapshot()
    addGptMessage(userMessage.content, documentStore.getDocumentIDs())
  }

  function addSystemMessage(content: string) {
    state.messageList.push({
      id: state.messageList.length,
      content,
      role: 'system',
      createdAt: Date.now(),
    })
    saveHistorySnapshot()
  }

  function addGptMessage(question: string, ids: string[]) {
    const requestToken = localStorage.getItem('token')
    const requestMessages = state.messageList
    const history = useChatHistoryStore()
    const sessionId = history.state.currentSessionId
    const documents = useDocumentListStore().getDocumentSnapshots()
    const selectedDocumentIDs = [...ids]
    const modelStore = useModelStore()
    const model = modelStore.currentModel
    const modelLabel = modelStore.getModelLabel(model)
    const newId = state.messageList.length
    const memory = useMemoryStore().getMemory
    let answer = ''
    let citations: CitationItem[] = []

    requestMessages.push({
      id: newId,
      content: '',
      role: 'gpt',
      model,
      modelLabel,
      createdAt: Date.now(),
      status: 'thinking',
    })

    function updateMessage(id: number, content: string) {
      if (requestToken !== localStorage.getItem('token')) return
      if (!requestMessages[id]) {
        requestMessages.push({
          id,
          content,
          role: 'gpt',
          model,
          modelLabel,
          createdAt: Date.now(),
          status: 'streaming',
        })
      } else {
        if (requestMessages[id].thinkingMs == null) {
          requestMessages[id].thinkingMs = Date.now() - (requestMessages[id].createdAt || Date.now())
        }
        requestMessages[id].content += content
        requestMessages[id].status = 'streaming'
      }
    }

    function saveRequestHistory(context = memory) {
      if (requestToken !== localStorage.getItem('token')) return
      history.saveSnapshot({
        title: requestMessages.find(message => message.role === 'user')?.content.slice(0, 24) || '新聊天',
        model, modelLabel, memory: context, summary: context, documents, selectedDocumentIDs,
        messages: requestMessages.filter(message => message.role === 'user' || message.role === 'gpt'),
      }, sessionId)
    }

    askQuestionStream(
      question,
      ids,
      model,
      memory,
      (text) => {
        answer += text
        updateMessage(newId, text)
      },
      (cits) => {
        citations = cits
      },
      (progress) => {
        if (requestToken === localStorage.getItem('token') && requestMessages[newId]) {
          const message = requestMessages[newId]
          message.searchStatus = progress.text
          message.searchState = progress.state
          if (progress.text && !message.searchSteps?.includes(progress.text)) {
            message.searchSteps = [...(message.searchSteps || []), progress.text]
          }
        }
      },
      (result) => {
        if (requestToken === localStorage.getItem('token') && requestMessages[newId]) {
          requestMessages[newId].externalPapers = result
        }
        saveRequestHistory()
      },
    )
      .then(() => {
        if (requestToken !== localStorage.getItem('token')) return
        if (requestMessages[newId]) {
          requestMessages[newId].citations = citations
          requestMessages[newId].status = 'done'
          requestMessages[newId].durationMs = Date.now() - (requestMessages[newId].createdAt || Date.now())
        }
        saveRequestHistory()
        notifyTaskCompletion('智能问答已完成', question, `/home/Chat?session=${encodeURIComponent(sessionId)}`, requestToken, history.state.currentSessionId !== sessionId)
        return updateMemory(question, memory, answer).catch(error => { console.error('更新对话记忆失败', error) })
      })
      .then((data: any) => {
        if (requestToken !== localStorage.getItem('token')) return
        if (data?.context && history.state.currentSessionId === sessionId) {
          useMemoryStore().setMemory(data.context)
        }
        saveRequestHistory(data?.context || memory)
      })
      .catch((error) => {
        console.error(error)
        if (requestToken !== localStorage.getItem('token')) return
        if (requestMessages[newId]) {
          requestMessages[newId].status = 'error'
          requestMessages[newId].durationMs ??= Date.now() - (requestMessages[newId].createdAt || Date.now())
        }
        requestMessages.push({ role: 'system', content: `模型调用失败：${error?.message || error}` })
        saveRequestHistory()
      })
  }

  function compressContextForModelSwitch(fromModel: string, toModel: string) {
    const recentMessages = state.messageList
      .filter(message => message.role !== 'system' && message.content.trim())
      .slice(-8)
      .map((message) => {
        const role = message.role === 'user' ? '用户' : '助手'
        return `${role}: ${message.content.trim()}`
      })
      .join('\n')
    const documents = useDocumentListStore().getDocumentSnapshots()
    const documentText = documents.length
      ? documents.map(item => item.documentName).join(', ')
      : '当前未绑定论文'

    const compressed = [
      `模型已从 ${fromModel} 切换为 ${toModel}。`,
      '以下是为降低跨模型上下文漂移而压缩后的对话记忆：',
      `当前论文上下文：${documentText}`,
      recentMessages || '暂无历史对话。',
    ].join('\n')

    useMemoryStore().setMemory(compressed.slice(-3000))
    saveHistorySnapshot()
  }

  function clearMessages() {
    state.messageList = []
    useMemoryStore().clearMemory()
    useDocumentListStore().clearDocuments()
    useChatHistoryStore().startNewSession()
  }

  function restoreMessages(messagesToRestore: Message[], memory = '') {
    state.messageList = messagesToRestore.filter(message => message.role === 'user' || message.role === 'gpt').map((message, index) => ({
      ...message,
      id: index,
    }))
    useMemoryStore().setMemory(memory)
  }

  function saveHistorySnapshot() {
    const firstUserMessage = state.messageList.find(message => message.role === 'user')
    const modelStore = useModelStore()
    useChatHistoryStore().saveSnapshot({
      title: firstUserMessage?.content.slice(0, 24) || '新聊天',
      model: modelStore.currentModel,
      modelLabel: modelStore.getModelLabel(modelStore.currentModel),
      memory: useMemoryStore().getMemory,
      summary: useMemoryStore().getMemory,
      documents: useDocumentListStore().getDocumentSnapshots(),
      selectedDocumentIDs: useDocumentListStore().getDocumentIDs(),
      messages: state.messageList.filter(message => message.role === 'user' || message.role === 'gpt'),
    })
  }

  return {
    state,
    messages,
    addUserMessage,
    addSystemMessage,
    clearMessages,
    restoreMessages,
    compressContextForModelSwitch,
    saveHistorySnapshot,
  }
})
