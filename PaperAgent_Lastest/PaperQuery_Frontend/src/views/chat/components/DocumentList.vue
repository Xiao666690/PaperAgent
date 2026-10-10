<template>
  <section v-if="documents.length" class="paper-selector" aria-label="本轮问答所用论文">
    <header class="scope-header"><div><span class="scope-icon"><BookOpen :size="15" /></span><strong>本轮论文范围</strong><span class="scope-count">已选 {{ selectedCount }} / {{ documents.length }} 篇</span></div><button type="button" @click="toggleAll">{{ allSelected ? '取消全选' : '全选' }}</button></header>
    <div class="paper-options">
      <div v-for="(document, index) in documents" :key="document.documentID || index" class="paper-option" :class="{ selected: isSelected(document.documentID) }">
        <button type="button" class="paper-select-button" :disabled="!document.documentID || document.isLoading" :aria-pressed="isSelected(document.documentID)" :title="document.documentName" @click="document.documentID && store.toggleDocument(document.documentID)"><span class="selection-mark"><Check v-if="isSelected(document.documentID)" :size="13" :stroke-width="2.5" /></span><span class="paper-option-copy"><strong>{{ document.documentName }}</strong><span>{{ document.source === 'library' ? '论文库' : '本地 PDF' }} · {{ document.isLoading ? '处理中' : isSelected(document.documentID) ? '本轮使用' : '本轮未选' }}</span></span></button>
        <button type="button" class="remove" :aria-label="`移除 ${document.documentName}`" :title="`移除 ${document.documentName}`" @click="store.deleteDocument(index)"><X :size="14" /></button>
      </div>
    </div>
    <p v-if="!selectedCount" class="scope-warning"><Info :size="13" /> 未选中论文，发送后将使用普通模型对话。</p>
  </section>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { BookOpen, Check, Info, X } from 'lucide-vue-next'
import { useDocumentListStore } from '@/stores/documentList'
const store = useDocumentListStore()
const documents = computed(() => store.state.documentList)
const selectedCount = computed(() => store.getDocumentIDs().length)
const availableIDs = computed(() => documents.value.filter(document => !document.isLoading && document.documentID).map(document => document.documentID!))
const isSelected = (id?: string) => !!id && store.state.selectedDocumentIDs.includes(id)
const allSelected = computed(() => availableIDs.value.length > 0 && availableIDs.value.every(isSelected))
const toggleAll = () => { store.state.selectedDocumentIDs = allSelected.value ? [] : [...availableIDs.value] }
</script>
<style scoped>
.paper-selector { width: 100%; min-width: 0; margin: 0 0 10px; padding: 12px; border: 1px solid #dae6f1; border-radius: 16px; background: #ffffffd9; box-shadow: 0 3px 14px #5298d905; }
.scope-header, .scope-header > div { display: flex; align-items: center; gap: 7px; }.scope-header { justify-content: space-between; margin-bottom: 9px; }.scope-header strong { color: #415363; font-size: 12px; font-weight: 600; }.scope-icon { color: #6995bf; }.scope-count { font-size: 11px; color: #70798b; }.scope-header > button { padding: 3px 7px; border-radius: 6px; color: #5298d9; font-size: 11px; }
.paper-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); max-height: 138px; overflow-y: auto; gap: 7px; padding: 2px; }.paper-option { display: flex; min-width: 0; align-items: center; border: 1px solid #e2e6f0; border-radius: 11px; background: #fafbfe; transition: background-color 160ms ease, border-color 160ms ease, box-shadow 160ms ease; }.paper-option.selected { border-color: #adcfef; background: #edf6ff; box-shadow: inset 2px 0 0 #75acdf; }
.paper-select-button { display: flex; align-items: center; flex: 1; min-width: 0; gap: 9px; padding: 9px 8px 9px 11px; text-align: left; border-radius: 10px; }.paper-select-button:active { transform: none; }
.selection-mark { display: grid; place-items: center; flex: none; width: 18px; height: 18px; border: 1px solid #b8c1d2; border-radius: 5px; background: white; color: white; transition: background-color 140ms ease, border-color 140ms ease; }.selected .selection-mark { background: #5298d9; border-color: #5298d9; }
.paper-option-copy { min-width: 0; }.paper-option-copy strong { display: block; color: #323d47; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; font-weight: 550; }.paper-option-copy > span { display: block; margin-top: 3px; color: #70798b; font-size: 10px; }.selected .paper-option-copy > span { color: #637d95; }
.remove { display: grid; place-items: center; flex: none; width: 28px; height: 28px; margin-right: 4px; border-radius: 7px; color: #818f9c; }.remove:hover { color: #be3e4d; background: #fff0f1; }
.scope-warning { display: flex; align-items: center; gap: 5px; margin: 9px 0 0; color: #925700; font-size: 11px; }
@media(max-width: 560px) { .paper-options { grid-template-columns: 1fr; max-height: 112px; }.scope-count { font-size: 10px; }.paper-selector { padding: 10px; } }
</style>
