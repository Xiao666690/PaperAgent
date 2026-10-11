<template>
  <div class="chat-footer">
    <div class="composer-stack">
      <DocumentList />
      <InputBox />
      <p class="composer-caption">回答基于本轮所选论文，请结合引用核查重要结论。</p>
    </div>
  </div>
</template>
<script setup lang="ts">
import DocumentList from '../../components/DocumentList.vue'
import InputBox from '../../components/InputBox.vue'
</script>
<style scoped>
.composer-stack { max-width: 800px; width: 100%; margin: 0 auto; }
.composer-caption { margin: 8px 0 0; color: #70798b; font-size: 11px; text-align: center; }
</style>
