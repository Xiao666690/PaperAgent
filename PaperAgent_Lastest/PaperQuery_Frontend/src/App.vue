<template>
  <div id="main router" class="app-router-root flex-grow h-full w-full min-w-0">
    <router-view :key="key" class="" />
  </div>
</template>

<script setup lang="ts">
import { isMobile, watchResize } from '@bassist/utils'
import { startTaskCompletionMonitor } from '@/services/taskCompletion'
const router = useRouter()
const stopCompletionMonitor = startTaskCompletionMonitor(router)
onBeforeUnmount(stopCompletionMonitor)
const route = useRoute()
// Reader panes own their scroll. Clip the document and mount root as well:
// overflow:hidden alone still allows focus/scrollIntoView to move an ancestor.
watch(() => route.name, name => {
  document.documentElement.classList.toggle('pa-reader-open', name === 'pdfInfo')
}, { immediate: true })
onBeforeUnmount(() => document.documentElement.classList.remove('pa-reader-open'))
// Reload panes when switching PDFs; a citation page change keeps the current PDF loaded.
const key = computed(() => route.path)

watchResize(() => {
  document.body.classList.remove('platform-mobile', 'platform-desktop')
  document.body.classList.add(`platform-${isMobile() ? 'mobile' : 'desktop'}`, 'pa-theme')
})
</script>
