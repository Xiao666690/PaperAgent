<template>
  <div id="main router" class="flex-grow h-full w-full min-w-0">
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
const key = computed(() => `${String(route.name || route.path)}-${new Date()}`)

watchResize(() => {
  document.body.classList.remove('platform-mobile', 'platform-desktop')
  document.body.classList.add(`platform-${isMobile() ? 'mobile' : 'desktop'}`, 'pa-theme')
})
</script>
