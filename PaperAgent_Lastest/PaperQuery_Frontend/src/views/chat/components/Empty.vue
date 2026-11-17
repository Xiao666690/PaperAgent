<template>
  <div class="chat-empty flex flex-col items-center justify-center w-full h-full">
    <div class="chat-empty-mark"><MessagesSquare :size="30" :stroke-width="1.6" /></div>
    <h2>让每一次探索，都有据可循</h2>
    <p>添加论文，选定本轮资料范围，再提出你的问题。一起发现方法、比较证据、形成新的研究思路。</p>
    <span class="chat-empty-hint"><BookOpen :size="14" /> 从下方「添加论文」开始</span>
  </div>
</template>
<script setup lang="ts">
import { MessagesSquare, BookOpen } from 'lucide-vue-next'
</script>
