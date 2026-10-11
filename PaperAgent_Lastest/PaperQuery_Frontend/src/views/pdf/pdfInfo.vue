<template>
  <div class="reader-workspace">
    <template v-if="isCompact">
      <nav class="reader-mobile-tabs" aria-label="阅读工具"><button v-for="item in readerTabs" :key="item.value" type="button" :aria-pressed="readerPane === item.value" :class="{ active: readerPane === item.value }" @click="readerPane = item.value">{{ item.label }}</button></nav>
      <div v-show="readerPane === 'paper'" class="reader-mobile-body"><pdfViewer :knowledge-i-d="knowledgeID" :document-i-d="documentID" @selection="onSelection" @loaded="readerReady = true" /></div>
      <div v-show="readerPane === 'tools'" class="reader-mobile-body"><translateBox :knowledge-id="knowledgeID" :document-id="documentID" /></div>
      <div v-show="readerPane === 'chat'" class="reader-mobile-body"><chat :knowledge-id="knowledgeID" :document-id="documentID" :selected-text="selectedText" :selected-page="selectedPage" @clear-selection="selectedText = ''" /></div>
    </template>
    <ResizablePanelGroup v-else id="group_1" direction="horizontal" class="w-full h-full">
      <ResizablePanel id="panel-1" :default-size="64" :min-size="0" :collapsed-size="0" collapsible class="h-full min-w-0">
        <div class="w-full h-full">
          <pdfViewer :knowledge-i-d="knowledgeID" :document-i-d="documentID" @selection="onSelection" @loaded="readerReady = true" />
        </div>
      </ResizablePanel>
      <ResizableHandle with-handle class="reader-handle" />
      <ResizablePanel id="panel-2" :default-size="36" :min-size="0" :collapsed-size="0" collapsible class="h-full min-w-0">
        <div class="flex flex-col w-full h-full min-w-0 overflow-hidden">
          <ResizablePanelGroup id="group_2" direction="vertical" class="h-full min-w-0 w-full">
            <ResizablePanel id="panel-2-1" :default-size="50" :min-size="0" :collapsed-size="0" collapsible class="h-full min-h-0">
              <div class="flex flex-1 h-full min-w-0 overflow-hidden">
                <translateBox :knowledge-id="knowledgeID" :document-id="documentID" />
              </div>
            </ResizablePanel>
            <ResizableHandle with-handle class="reader-handle" />
            <ResizablePanel id="panel-2-2" :default-size="50" :min-size="0" :collapsed-size="0" collapsible class="h-full min-h-0">
              <div class="flex flex-1 h-full min-w-0 overflow-hidden">
                <chat class="flex-1" :knowledge-id="knowledgeID" :document-id="documentID" :selected-text="selectedText" :selected-page="selectedPage" @clear-selection="selectedText = ''" />
              </div>
            </ResizablePanel>
          </ResizablePanelGroup>
        </div>
      </ResizablePanel>
    </ResizablePanelGroup>
  </div>
</template>

<style scoped>
.reader-workspace { display: flex; flex: 1 1 0%; width: 100%; height: 100vh; min-width: 0; min-height: 0; overflow: clip; }
.reader-handle { z-index: 10; background: #d4d9e5; transition: background-color .18s ease, box-shadow .18s ease; }
.reader-handle:hover, .reader-handle:focus-visible { background: #568fc5; box-shadow: 0 0 0 3px rgba(103,86,197,.16); }
.reader-handle :deep(div) { width: 18px; height: 24px; color: #487cad; background: #fff; border: 1px solid #a1bcd6; }
.reader-mobile-tabs { display: flex; flex: none; gap: 5px; padding: 8px 12px; border-bottom: 1px solid #e2e6f0; background: #fff; }
.reader-mobile-tabs button { flex: 1; padding: 8px 10px; border-radius: 9px; color: #586174; font-size: 13px; }
.reader-mobile-tabs button.active { color: #5298d9; background: #eaf4fe; }
.reader-mobile-body { flex: 1; min-height: 0; width: 100%; }
@media(max-width:800px) { .reader-workspace { flex-direction: column; } }
</style>

<script setup lang="ts">
import pdfViewer from '@/views/pdf/pdfViewer.vue'
import chat from '@/views/smallChat/chat.vue'
import translateBox from '@/views/translate/translateBox.vue'
import { useRoute } from 'vue-router'
import { recordReading } from '@/api/dashboard'
import { useMediaQuery } from '@vueuse/core'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/components/ui/resizable'

const route = useRoute()

const knowledgeID = route.params.knowledgeID as string
const documentID = route.params.documentID as string
const selectedText = ref('')
const selectedPage = ref(1)
const readerReady = ref(false)
const isCompact = useMediaQuery('(max-width: 800px)')
const readerPane = ref('paper')
const readerTabs = [{value:'paper',label:'论文阅读'}, {value:'tools',label:'翻译 / 笔记'}, {value:'chat',label:'论文问答'}]
const onSelection = (text: string, page: number) => {
  selectedText.value = text
  selectedPage.value = page
}

let readingTimer: ReturnType<typeof setInterval> | undefined
let lastReadingTick = Date.now()
const captureReading = () => {
  const now = Date.now()
  const seconds = Math.min(30, Math.floor((now - lastReadingTick) / 1000))
  lastReadingTick = now
  if (readerReady.value && seconds > 0 && document.visibilityState === 'visible' && document.hasFocus()) {
    recordReading(knowledgeID, documentID, seconds).catch(error => console.error('阅读时长记录失败', error))
  }
}
onMounted(() => { lastReadingTick = Date.now(); readingTimer = setInterval(captureReading, 15000) })
onBeforeUnmount(() => { clearInterval(readingTimer); captureReading() })
</script>
