<template>
  <div id="home" class="app-shell flex min-h-screen" :class="{ 'reader-shell': route.path.toLowerCase().includes('/pdfinfo/') }">
    <SideBar
      :is-collapsed="isCollapsed"
      @toggle-collapse="isCollapsed = !isCollapsed"
    />
    <router-view class="min-w-0 flex-1" />
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const isCollapsed = ref(false)
</script>

<style lang="less" scoped>
.app-shell { width: 100%; min-width: 0; overflow-x: clip; background: #f7f9ff; }
.reader-shell { height: 100dvh; min-height: 0; overflow: hidden; }
.reader-shell :deep(.reader-workspace) { height: 100%; flex-basis: auto; }
@media (max-width: 560px) {
  .app-shell { padding-bottom: 68px; }
}
</style>
