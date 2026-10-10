<!-- 这是内容区域 -->
<template>
  <div class="chat-content flex flex-col overflow-hidden min-h-0">
    <Header class="flex-none" />
    <Main class="flex-1 min-h-0" />
    <Footer class="flex-none" />
  </div>
</template>

<style lang="scss" scoped></style>

<script setup lang="ts">
import Header from './components/HeaderArea.vue'
import Main from './components/MainArea.vue'
import Footer from './components/FooterArea.vue'
</script>
