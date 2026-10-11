<template>
  <div class="paper-upload-control">
    <el-button circle class="upload-trigger" aria-label="添加论文" title="添加论文" @click="openDialog"><Plus :size="21" /></el-button>
    <el-dialog v-model="dialogVisible" class="paper-picker-dialog" width="760px" append-to-body :close-on-click-modal="!submitting" :close-on-press-escape="!submitting" :show-close="!submitting" :before-close="handleClose">
      <template #header><div class="picker-heading"><span class="picker-heading-icon"><LibraryBig :size="23" /></span><div><h2>为对话添加论文</h2><p>选定资料范围，让每个回答都有证据可循。</p></div></div></template>
      <el-tabs v-model="sourceMode" class="picker-tabs" :before-leave="() => !submitting">
        <el-tab-pane name="library"><template #label><span class="picker-tab-label"><LibraryBig :size="16" /> 论文库</span></template>
          <div class="picker-library-tools"><label class="picker-field-label">选择知识库</label>
            <el-select v-model="selectedKnowledgeID" :disabled="knowledgeLoading" :loading="knowledgeLoading" placeholder="选择你的知识库" aria-label="选择知识库" @change="loadDocuments"><el-option v-for="knowledge in knowledgeList" :key="knowledge.knowledgeID" :label="`${knowledge.knowledgeName}（${knowledge.documentNum || 0} 篇）`" :value="knowledge.knowledgeID" /></el-select>
            <el-input v-model="search" clearable placeholder="搜索论文名称" aria-label="搜索论文名称"><template #prefix><Search :size="16" /></template></el-input>
          </div>
          <div class="picker-list-heading"><span>{{ search ? `搜索结果 ${filteredDocuments.length} 篇` : `共 ${libraryDocuments.length} 篇论文` }}</span><button type="button" :disabled="!selectableDocuments.length || libraryLoading" @click="toggleVisibleSelection">{{ allVisibleSelected ? '取消当前结果选择' : '全选可用论文' }}</button></div>
          <div v-loading="libraryLoading || knowledgeLoading" class="picker-paper-list">
            <div v-if="!libraryLoading && !knowledgeLoading && filteredDocuments.length === 0" class="picker-empty"><FileSearch :size="34" /><strong>{{ search ? '没有找到匹配的论文' : '这里还没有论文' }}</strong><p>{{ search ? '试试更短的关键词，或清空搜索。' : '选择其他知识库，或上传本地 PDF。' }}</p></div>
            <el-checkbox-group v-else v-model="selectedDocumentIDs" aria-label="可添加的论文">
              <el-checkbox v-for="document in filteredDocuments" :key="document.documentID" :value="document.documentID" :disabled="document.documentStatus !== 2" class="picker-paper" :class="{ 'picker-paper-selected': selectedDocumentIDs.includes(document.documentID) }">
                <span class="picker-paper-content"><span class="picker-paper-icon"><FileText :size="22" :stroke-width="1.6" /></span><span class="picker-paper-copy"><strong :title="document.documentName">{{ document.documentName }}</strong><span class="picker-paper-meta"><span>PDF 文档</span><span class="picker-status" :class="{ ready: document.documentStatus === 2 }"><span class="picker-status-dot" />{{ document.documentStatus === 2 ? '可用于问答' : document.documentStatus === 1 ? '处理中，暂不可选' : '等待处理，暂不可选' }}</span></span></span><span v-if="selectedDocumentIDs.includes(document.documentID)" class="picker-selected-label">已选</span></span>
              </el-checkbox>
            </el-checkbox-group>
          </div>
          <div v-if="selectedDocumentIDs.length" class="picker-selection-summary"><span class="summary-icon"><Check :size="14" /></span><span>已选 <strong>{{ selectedDocumentIDs.length }}</strong> 篇论文</span><button type="button" @click="selectedDocumentIDs = []">清空选择</button></div>
          <p class="picker-help"><ShieldCheck :size="14" /> 仅处理完成的论文可以加入；发送问题前可再次调整本轮范围。</p>
        </el-tab-pane>
        <el-tab-pane name="upload"><template #label><span class="picker-tab-label"><Upload :size="16" /> 本地 PDF</span></template>
          <input ref="fileInput" class="hidden" type="file" accept=".pdf,application/pdf" multiple @change="handleFileSelect" />
          <button type="button" class="picker-upload-zone" :class="{ dragging }" :disabled="submitting" @click="fileInput?.click()" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop.prevent="handleDrop"><span class="upload-zone-icon"><Upload :size="27" /></span><strong>点击选择或拖入 PDF 论文</strong><span>支持多篇论文，上传后即可用于当前对话</span></button>
          <div v-if="pendingFiles.length" class="picker-file-list"><div v-for="(file, index) in pendingFiles" :key="`${file.name}-${file.size}-${file.lastModified}`" class="picker-file"><FileText :size="18" /><div><strong>{{ file.name }}</strong><span>{{ formatSize(file.size) }}</span></div><button type="button" :disabled="submitting" :aria-label="`移除 ${file.name}`" @click="pendingFiles.splice(index, 1)"><X :size="16" /></button></div></div>
          <div class="picker-library-option"><span class="library-option-icon"><FolderPlus :size="21" /></span><div><strong>同时保存到论文库</strong><p>关闭时仅绑定当前对话，不加入长期资料库。</p></div><el-switch v-model="addToLibrary" :disabled="submitting" aria-label="同时保存到论文库" /></div>
          <Transition name="picker-field"><el-select v-if="addToLibrary" v-model="uploadKnowledgeID" :disabled="submitting" class="picker-destination" placeholder="选择目标知识库" aria-label="目标知识库"><el-option v-for="knowledge in knowledgeList" :key="knowledge.knowledgeID" :label="knowledge.knowledgeName" :value="knowledge.knowledgeID" /></el-select></Transition>
        </el-tab-pane>
      </el-tabs>
      <template #footer><div class="picker-footer"><span aria-live="polite">{{ sourceMode === 'library' ? `已选择 ${selectedDocumentIDs.length} 篇` : `待上传 ${pendingFiles.length} 篇` }}</span><div><el-button :disabled="submitting" @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="submitting" :disabled="!canConfirm" @click="confirmSelection"><Plus v-if="!submitting" :size="16" />添加到对话</el-button></div></div></template>
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import { Check, FileSearch, FileText, FolderPlus, LibraryBig, Plus, Search, ShieldCheck, Upload, X } from 'lucide-vue-next'
import { ElMessage, ElNotification } from 'element-plus'
import { computed, ref } from 'vue'
import { getDocumentList, getKnowledgeList } from '@/api/data'
import { uploadFile } from '@/api/chat'
import { useDocumentListStore, type Document } from '@/stores/documentList'
import { formatSize } from '@/utils/format'
type Knowledge = { knowledgeID: string; knowledgeName: string; documentNum?: number }
type LibraryDocument = { documentID: string; documentName: string; documentStatus: number; vectorNum?: number }
const dialogVisible = ref(false)
const sourceMode = ref<'library' | 'upload'>('library')
const knowledgeList = ref<Knowledge[]>([])
const selectedKnowledgeID = ref('')
const libraryDocuments = ref<LibraryDocument[]>([])
const selectedDocumentIDs = ref<string[]>([])
const libraryLoading = ref(false)
const knowledgeLoading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const pendingFiles = ref<File[]>([])
const addToLibrary = ref(false)
const uploadKnowledgeID = ref('')
const submitting = ref(false)
const search = ref('')
const dragging = ref(false)
let documentRequest = 0
const filteredDocuments = computed(() => libraryDocuments.value.filter(document => document.documentName.toLowerCase().includes(search.value.trim().toLowerCase())))
const selectableDocuments = computed(() => filteredDocuments.value.filter(document => document.documentStatus === 2))
const allVisibleSelected = computed(() => selectableDocuments.value.length > 0 && selectableDocuments.value.every(document => selectedDocumentIDs.value.includes(document.documentID)))
const canConfirm = computed(() => !libraryLoading.value && !knowledgeLoading.value && (sourceMode.value === 'library' ? selectedDocumentIDs.value.length > 0 : pendingFiles.value.length > 0 && (!addToLibrary.value || !!uploadKnowledgeID.value)))
function toggleVisibleSelection() {
  const ids = selectableDocuments.value.map(document => document.documentID)
  selectedDocumentIDs.value = allVisibleSelected.value ? selectedDocumentIDs.value.filter(id => !ids.includes(id)) : [...new Set([...selectedDocumentIDs.value, ...ids])]
}
function handleClose(done: () => void) { if (!submitting.value) done() }
async function openDialog() {
  dialogVisible.value = true
  knowledgeLoading.value = true
  try {
    const response = await getKnowledgeList()
    knowledgeList.value = response.data?.knowledgeList || []
    if (!knowledgeList.value.some(knowledge => knowledge.knowledgeID === selectedKnowledgeID.value)) selectedKnowledgeID.value = knowledgeList.value[0]?.knowledgeID || ''
    await loadDocuments()
  } catch (error: any) { ElMessage.error(error?.message || '读取论文库失败') }
  finally { knowledgeLoading.value = false }
}
async function loadDocuments() {
  const request = ++documentRequest
  selectedDocumentIDs.value = []
  libraryDocuments.value = []
  search.value = ''
  if (!selectedKnowledgeID.value) { libraryLoading.value = false; return }
  libraryLoading.value = true
  try {
    const response = await getDocumentList(selectedKnowledgeID.value)
    if (request === documentRequest) libraryDocuments.value = response.data || []
  } catch (error: any) { if (request === documentRequest) ElMessage.error(error?.message || '读取论文列表失败') }
  finally { if (request === documentRequest) libraryLoading.value = false }
}
function acceptFiles(files: File[]) {
  const valid = files.filter(file => file.name.toLowerCase().endsWith('.pdf'))
  if (valid.length !== files.length) ElMessage.warning('仅支持 PDF 文件，其他格式已忽略')
  const known = new Set(pendingFiles.value.map(file => `${file.name}:${file.size}:${file.lastModified}`))
  pendingFiles.value.push(...valid.filter(file => { const key = `${file.name}:${file.size}:${file.lastModified}`; if (known.has(key)) return false; known.add(key); return true }))
}
function handleFileSelect(event: Event) { const input = event.target as HTMLInputElement; acceptFiles(Array.from(input.files || [])); input.value = '' }
function handleDrop(event: DragEvent) { dragging.value = false; if (!submitting.value) acceptFiles(Array.from(event.dataTransfer?.files || [])) }
async function confirmSelection() {
  if (submitting.value || !canConfirm.value) return
  const store = useDocumentListStore()
  const previousSelection = [...store.state.selectedDocumentIDs]
  if (sourceMode.value === 'library') {
    let added = 0
    const chosen = libraryDocuments.value.filter(item => item.documentStatus === 2 && selectedDocumentIDs.value.includes(item.documentID))
    for (const item of chosen) {
      const document: Document = { documentID: item.documentID, documentName: item.documentName, knowledgeID: selectedKnowledgeID.value, source: 'library', isLoading: false }
      if (store.appendDocument(document)) added += 1
    }
    // Multi-select confirmation keeps all chosen papers active, rather than just
    // the last item selected by appendDocument's single-add default.
    store.state.selectedDocumentIDs = [...new Set([...previousSelection, ...chosen.map(item => item.documentID)])]
    dialogVisible.value = false
    ElMessage.success(added ? `已添加 ${added} 篇论文，可在下方调整本轮范围` : '已更新本轮论文选择')
    return
  }
  submitting.value = true
  const uploadedIDs: string[] = []
  let added = 0
  try {
    // Consume successful files so a partial-failure retry won't upload them twice.
    while (pendingFiles.value.length) {
      const file = pendingFiles.value[0]
      const data = await uploadFile(file, { addToLibrary: addToLibrary.value, knowledgeID: addToLibrary.value ? uploadKnowledgeID.value : undefined })
      const document: Document = { documentID: data.documentID, documentName: data.documentName || file.name, documentFile: file, fileSize: file.size, knowledgeID: data.knowledgeID || undefined, source: 'upload', isLoading: false }
      if (store.appendDocument(document)) added += 1
      if (data.documentID) uploadedIDs.push(data.documentID)
      pendingFiles.value.shift()
    }
    dialogVisible.value = false
    ElNotification.success(addToLibrary.value ? `已上传并保存到论文库，共 ${added} 篇` : `已上传到当前对话，共 ${added} 篇`)
  } catch (error: any) { ElMessage.error(error?.message || '上传失败，未完成的文件已保留，可重试') }
  finally {
    store.state.selectedDocumentIDs = [...new Set([...previousSelection, ...uploadedIDs])]
    submitting.value = false
  }
}
</script>
<style scoped>
.upload-trigger { width: 42px; height: 42px; border: 1px solid #caddef; color: #5298d9; background: #f0f8ff; border-radius: 13px; }
.upload-trigger:hover { background: #e4f2ff; border-color: #98c0e6; }
.picker-heading { display: flex; align-items: center; gap: 13px; padding-right: 24px; }.picker-heading-icon { display: grid; place-items: center; width: 48px; height: 48px; flex: none; border: 1px solid #d5e7f7; border-radius: 15px; color: #5298d9; background: linear-gradient(140deg, #f8fcff, #e7f3ff); }
.picker-heading h2 { margin: 0; color: #202438; font-size: 21px; font-weight: 650; }.picker-heading p { margin: 5px 0 0; color: #586174; font-size: 13px; line-height: 1.6; }
.picker-tab-label { display: inline-flex; align-items: center; gap: 7px; }.picker-tabs { margin-top: 10px; }.picker-tabs :deep(.el-tabs__header) { margin-bottom: 18px; }.picker-tabs :deep(.el-tabs__item) { font-size: 14px; font-weight: 550; }
.picker-library-tools { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }.picker-field-label { grid-column: 1 / -1; color: #586174; font-size: 12px; font-weight: 550; }
.picker-list-heading { display: flex; justify-content: space-between; align-items: center; margin: 18px 2px 10px; color: #70798b; font-size: 12px; }.picker-list-heading button, .picker-selection-summary button { color: #5298d9; border-radius: 6px; padding: 4px 6px; }.picker-list-heading button:disabled { color: #989faf; }
.picker-paper-list { min-height: 180px; max-height: min(340px, 40dvh); overflow-y: auto; padding: 2px 4px 2px 2px; }.picker-paper-list :deep(.el-checkbox-group) { display: grid; gap: 9px; }
.picker-paper-list :deep(.el-checkbox) { width: 100%; height: auto; min-height: 78px; margin: 0; padding: 13px 15px; border: 1px solid #e2e6f0; border-radius: 13px; background: #fff; box-sizing: border-box; transition: border-color 160ms ease, background-color 160ms ease, box-shadow 180ms ease; }
.picker-paper-list :deep(.el-checkbox:hover:not(.is-disabled)) { border-color: #b5d2ed; background: #f9fcff; }.picker-paper-list :deep(.el-checkbox.is-checked) { border-color: #9bc4ea; background: linear-gradient(100deg, #eff7ff, #fcfbff); box-shadow: inset 3px 0 0 #70a9df, 0 3px 10px #5298d908; }.picker-paper-list :deep(.el-checkbox.is-disabled) { background: #f8f9fc; }
.picker-paper-list :deep(.el-checkbox__label) { display: block; flex: 1; min-width: 0; padding-left: 14px; white-space: normal; }.picker-paper-list :deep(.el-checkbox__inner) { width: 20px; height: 20px; border-radius: 6px; border-color: #b8c1d2; transition: border-color 140ms ease, background-color 140ms ease; }.picker-paper-list :deep(.el-checkbox.is-checked .el-checkbox__inner) { background: #5298d9; border-color: #5298d9; }.picker-paper-list :deep(.el-checkbox__inner::after) { left: 6px; top: 3px; height: 8px; width: 4px; }
.picker-paper-content { display: flex; align-items: center; gap: 12px; min-width: 0; }.picker-paper-icon { display: grid; place-items: center; flex: none; width: 39px; height: 43px; border: 1px solid #e1e8ef; border-radius: 10px; color: #8094a6; background: #faf9fd; }.picker-paper-selected .picker-paper-icon { color: #5298d9; border-color: #cce1f4; background: #e6f3ff; }
.picker-paper-copy { flex: 1; min-width: 0; }.picker-paper-copy strong { display: block; color: #202438; font-size: 14px; font-weight: 550; line-height: 1.5; overflow-wrap: anywhere; }.picker-paper-meta { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 5px; color: #70798b; font-size: 11px; }.picker-status { display: inline-flex; align-items: center; gap: 5px; color: #925700; }.picker-status.ready { color: #187a5a; }.picker-status-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.picker-selected-label { flex: none; border-radius: 6px; padding: 4px 7px; color: #5298d9; background: #dfeefc; font-size: 11px; }
.picker-selection-summary { display: flex; align-items: center; gap: 8px; padding: 10px 12px; margin-top: 12px; border: 1px solid #d7e6f4; border-radius: 11px; color: #496c8c; background: #f2f9ff; font-size: 12px; }.picker-selection-summary button { margin-left: auto; }.summary-icon { display: grid; place-items: center; width: 20px; height: 20px; border-radius: 50%; color: white; background: #72a8db; }
.picker-help { display: flex; gap: 6px; align-items: flex-start; color: #70798b; margin: 13px 0 0; font-size: 12px; line-height: 1.6; }.picker-help svg { margin-top: 2px; flex: none; }
.picker-empty { display: flex; min-height: 180px; align-items: center; justify-content: center; flex-direction: column; gap: 10px; color: #95abbf; }.picker-empty strong { color: #586174; font-size: 14px; font-weight: 550; }.picker-empty p { color: #70798b; font-size: 12px; text-align: center; }
.picker-upload-zone { display: flex; width: 100%; flex-direction: column; align-items: center; gap: 9px; padding: 30px 20px; border: 1px dashed #a8c7e4; border-radius: 16px; background: linear-gradient(135deg, #f8fcff, #faf9fd); color: #5298d9; }.picker-upload-zone.dragging { background: #e7f3ff; border-color: #5298d9; }.upload-zone-icon { display: grid; place-items: center; width: 56px; height: 56px; border-radius: 17px; background: #e7f3ff; margin-bottom: 4px; }.picker-upload-zone strong { font-size: 15px; font-weight: 550; }.picker-upload-zone > span:last-child { font-size: 12px; color: #70798b; }
.picker-file-list { max-height: 150px; overflow-y: auto; margin-top: 12px; }.picker-file { display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #e2e6f0; padding: 10px 4px; color: #769bbd; }.picker-file > div { flex: 1; min-width: 0; }.picker-file strong { display: block; font-size: 13px; font-weight: 500; color: #202438; overflow-wrap: anywhere; }.picker-file span { font-size: 11px; color: #70798b; }.picker-file button { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 8px; }
.picker-library-option { display: flex; align-items: center; gap: 11px; padding: 15px; margin-top: 18px; border: 1px solid #e2e6f0; border-radius: 13px; background: #fcfbff; }.library-option-icon { color: #769bbd; }.picker-library-option > div { flex: 1; }.picker-library-option strong { font-size: 13px; color: #202438; font-weight: 550; }.picker-library-option p { margin-top: 3px; color: #70798b; font-size: 12px; line-height: 1.6; }.picker-destination { width: 100%; margin-top: 12px; }
.picker-field-enter-active, .picker-field-leave-active { transition: opacity 180ms var(--ease-out), transform 180ms var(--ease-out); }.picker-field-enter-from, .picker-field-leave-to { opacity: 0; transform: translateY(-4px); }
.picker-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.picker-footer > span { color: #70798b; font-size: 12px; }.picker-footer > div { display: flex; gap: 8px; }.picker-footer .el-button + .el-button { margin-left: 0; }
@media (max-width: 560px) { .picker-heading h2 { font-size: 18px; }.picker-heading p { font-size: 12px; }.picker-library-tools { grid-template-columns: 1fr; }.picker-paper-list :deep(.el-checkbox) { padding: 12px 10px; }.picker-paper-icon { display: none; }.picker-selected-label { display: none; }.picker-footer { flex-wrap: wrap; }.picker-paper-list { max-height: 32dvh; } }
</style>
