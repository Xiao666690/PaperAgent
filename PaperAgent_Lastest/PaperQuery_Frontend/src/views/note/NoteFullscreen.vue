<template>
  <div class="note-fullscreen">
    <header class="fullscreen-bar">
      <button
        type="button"
        class="back-btn"
        
        title="返回论文阅读页"
        @click="onBackClick"
        
      >← 返回</button>
      <span class="bar-title">笔记全屏编辑</span>
    </header>
    <div class="fullscreen-body">
      <ResizablePanelGroup id="note_full_1" direction="horizontal" class="w-full h-full">
        <ResizablePanel id="note-full-panel-1" :default-size="55" :min-size="0" :collapsed-size="0" collapsible class="h-full min-w-0">
          <div class="w-full h-full">
            <pdfViewer :knowledge-i-d="knowledgeID" :document-i-d="documentID" />
          </div>
        </ResizablePanel>
        <ResizableHandle with-handle class="note-full-handle" />
        <ResizablePanel id="note-full-panel-2" :default-size="45" :min-size="0" :collapsed-size="0" collapsible class="h-full min-w-0">
          <div class="note-paper">
            <note class="w-full h-full" :knowledgeID="knowledgeID" :documentID="documentID" :hide-fullscreen="true"></note>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  </div>
</template>

<style scoped>
.note-fullscreen { display: flex; flex-direction: column; width: 100%; height: 100vh; min-width: 0; min-height: 0; overflow: clip; }
/* 顶部返回栏 */
.fullscreen-bar { display: flex; align-items: center; gap: 12px; flex: none; height: 44px; padding: 0 14px; background: #f7f9ff; border-bottom: 1px solid #e0e8f0; }
.back-btn { display: inline-flex; align-items: center; gap: 4px; border: none; border-radius: 8px; padding: 5px 12px; font-size: 13px; background: rgba(109,91,208,.12); color: #4b86bd; cursor: pointer; transition: background .15s ease; }
.back-btn:hover { background: rgba(109,91,208,.20); }
.bar-title { font-size: 13px; color: #64748b; }
.fullscreen-body { flex: 1 1 0%; min-height: 0; min-width: 0; }
.note-full-handle { z-index: 10; background: #d4d9e5; transition: background-color .18s ease, box-shadow .18s ease; }
.note-full-handle:hover, .note-full-handle:focus-visible { background: #568fc5; box-shadow: 0 0 0 3px rgba(103,86,197,.16); }
.note-full-handle :deep(div) { width: 18px; height: 24px; color: #487cad; background: #fff; border: 1px solid #a1bcd6; }

/* 笔记区：无卡片/圆角/投影/留白，直接铺满右面板 */
.note-paper {
  position: relative;
  height: 100%;
  width: 100%;
  background: transparent;
  border-radius: 0;
  box-shadow: none;
  padding: 0;
  overflow: hidden;
}

</style>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import pdfViewer from '@/views/pdf/pdfViewer.vue'
import note from '@/views/note/note.vue'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/components/ui/resizable'

const route = useRoute()
const router = useRouter()
const knowledgeID = route.params.knowledgeID as string
const documentID = route.params.documentID as string
const goBack = () => {
  // 优先回退到来源页；无历史（如直接刷新进入）则回论文阅读页
  if (window.history.length > 1) router.back()
  else router.push({ name: 'pdfInfo', params: { knowledgeID, documentID } })
}
const onBackClick = () => goBack()
</script>
