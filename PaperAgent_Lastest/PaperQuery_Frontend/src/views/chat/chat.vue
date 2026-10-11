<template>
  <div class="chat-workspace">
    <button v-if="isCompact" type="button" class="mobile-history-button" aria-label="打开历史会话" @click="historyOpen = true"><History :size="19" /></button>
    <ResizablePanelGroup direction="horizontal" class="h-full w-full">
      <ResizablePanel :default-size="isCompact ? 100 : 76" :min-size="45" class="min-w-0"><Content class="h-full min-w-0" /></ResizablePanel>
      <ResizableHandle v-if="!isCompact" with-handle class="chat-handle" />
      <ResizablePanel v-if="!isCompact" :default-size="24" :min-size="0" :collapsed-size="0" collapsible class="min-w-0"><SideBar class="h-full" /></ResizablePanel>
    </ResizablePanelGroup>
    <el-drawer v-if="isCompact" v-model="historyOpen" title="历史会话" size="min(360px, 90vw)" append-to-body><SideBar /></el-drawer>
  </div>
</template>

<style scoped>
.chat-workspace { position: relative; display: flex; height: 100vh; min-width: 0; overflow: hidden; }
.mobile-history-button { position: absolute; top: 14px; right: 14px; z-index: 25; display: grid; place-items: center; width: 36px; height: 36px; border: 1px solid #d1deeb; border-radius: 10px; color: #5298d9; background: #fff; }
.chat-handle { z-index: 10; background: #d8dcdf; transition: background-color .18s ease; }
.chat-handle:hover, .chat-handle:focus-visible { background: #5b97d0; }
</style>

<script setup lang="ts">
import Content from './content/ContentView.vue'
import SideBar from './sidebar/SideBar.vue'
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable'
import { History } from 'lucide-vue-next'
import { useMediaQuery } from '@vueuse/core'
import { useChatHistoryStore } from '@/stores/chatHistory'
import { useMessageListStore } from '@/stores/messageList'
import { useDocumentListStore } from '@/stores/documentList'
import { useModelStore, type ModelType } from '@/stores/modelStore'
const route = useRoute()
watch(() => route.query.session, (id) => {
  if (typeof id !== 'string') return
  const history = useChatHistoryStore()
  const session = history.state.sessions.find(item => item.id === id)
  if (!session) return
  history.useSession(id)
  useModelStore().setModel(session.model as ModelType)
  useMessageListStore().restoreMessages(session.messages, session.memory)
  useDocumentListStore().restoreDocuments(session.documents || [], session.selectedDocumentIDs)
}, { immediate: true })
const isCompact = useMediaQuery('(max-width: 900px)')
const historyOpen = ref(false)
// import { useMessageListStore } from '@/stores/messageList'
</script>
