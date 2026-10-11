<script setup lang="ts">
// import { Button } from '@/components/ui/button'
import TodayOverview from './TodayOverview.vue'
import { Button } from '@/components/ui/button'
import { useStore } from 'vuex'

const store = useStore()
const router = useRouter()

const logoutButton = () => {
  store.dispatch('logout')
  router.push('/login')
}
</script>

<template>
  <div class="dashboard-shell pa-page" role="region" aria-label="概览内容" tabindex="0">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold">概览</h1>
      <Button variant="outline" class="text-1xl" @click="logoutButton"
        >注销</Button
      >
    </div>
    <TodayOverview />
  </div>
</template>

<style scoped>
.dashboard-shell { flex: 1 1 0; width: auto; max-width: 1600px; min-width: 0; min-height: 0; height: 100dvh; margin: 0 auto; padding: 22px clamp(16px, 2.5vw, 40px) 48px; overflow-y: auto; overflow-x: hidden; scrollbar-gutter: stable; overscroll-behavior-y: contain; scroll-behavior: auto; }
.dashboard-shell:focus-visible { outline: 2px solid var(--pa-brand); outline-offset: -2px; }
@media(max-width:560px) { .dashboard-shell { height: calc(100dvh - 68px - env(safe-area-inset-bottom)); } }
</style>
