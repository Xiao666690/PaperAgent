<!-- 这是一个输入框 -->
<template>
  <div class="composer-box flex items-end m-auto">
    <FileUploader />
    <el-input
      id="input_1"
      v-model="input"
      class="textarea"
      type="textarea"
      :autosize="{ minRows: 1, maxRows: 8 }"
      placeholder="请输入你的问题"
      resize="none"
      @keydown.enter="handleInputKeydown"
    />
    <div>
      <button type="button" class="send-button" :class="{ busy: isResponding }" :disabled="!isResponding && !input.trim()" :aria-label="isResponding ? '停止回答' : '发送问题'" :title="isResponding ? '停止回答，保留已生成内容' : '发送问题'" @click="isResponding ? messageList.stopCurrentAnswer() : handleButtonClick()">
        <Square v-if="isResponding" :size="17" fill="currentColor" :stroke-width="0" aria-hidden="true" />
        <ArrowUp v-else :size="22" :stroke-width="2.4" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>

<style lang="less" scoped>
.send-button { display: grid; place-items: center; flex: none; width: 42px; height: 42px; padding: 0; border-radius: 13px; background: var(--pa-brand, #147bdf); color: white; transition: background-color 160ms ease, opacity 160ms ease; }
.send-button:disabled { background: #e9eef4; color: #94a3b8; cursor: not-allowed; }.send-button.busy { background: #e8f3ff; color: #147bdf; }.send-spinner { animation: send-spin 1s linear infinite; }
@keyframes send-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .send-spinner { animation: none; }.send-button { transition: none; } }
@focus-border-color: #000000;

.el-button {
  border-radius: 10px;
  background-color: #e1f0ff;
  --el-button-hover-border-color: #d9e4ee;
  --el-button-border-color: #e1e9f0;
  --el-button-disabled-border-color: transparent;
  --el-button-disabled-bg-color: none;
  --el-button-active-border-color: #c7d6e5;
}
.composer-box :deep(.el-button:hover) { background: #c9e5ff; }

.composer-box { border: 1px solid #e3e3e6; border-radius: 18px; background: #fff; box-shadow: 0 7px 24px rgba(32,32,36,.07); transition: border-color .18s ease, box-shadow .18s ease; }
.composer-box:focus-within { border-color: #c8d8e7; box-shadow: 0 8px 28px rgba(74,62,137,.10), 0 0 0 3px rgba(109,91,208,.07); }

.el-textarea {
  font-family:
    ui-sans-serif,
    -apple-system,
    system-ui,
    Segoe UI,
    Roboto,
    Ubuntu,
    Cantarell,
    Noto Sans,
    sans-serif,
    Helvetica,
    Apple Color Emoji,
    Arial,
    Segoe UI Emoji,
    Segoe UI Symbol;
  font-size: 1rem;
  --el-input-focus-border-color: none;
  --el-input-bg-color: none;
  --el-input-border-color: none;
  --el-input-hover-border-color: none;
}
</style>

<script setup lang="ts">
import { ArrowUp, Square } from 'lucide-vue-next'

import { ref, computed } from 'vue'

import { useMessageListStore } from '@/stores/messageList'

import FileUploader from './DocumentUploader.vue'

const input = ref('')
const messageList = useMessageListStore()
const isResponding = computed(() => messageList.messages.some(message => message.status === 'thinking' || message.status === 'streaming'))

// 在这里处理按钮点击事件 向gpt发送问题
const handleButtonClick = () => {
  if (!input.value.trim() || isResponding.value) {
    return
  }
  const question = input.value
  input.value = ''
  messageList.addUserMessage({
    role: 'user',
    content: question,
  })
}
const handleInputKeydown = (event: KeyboardEvent) => {
  if (event.isComposing || event.keyCode === 229 || event.shiftKey) return
  event.preventDefault()
  handleButtonClick()
}
</script>
