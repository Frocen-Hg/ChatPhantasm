<script setup lang="ts">
defineProps<{ msg: { role: 'user' | 'assistant'; content: string; loading?: boolean } }>()
</script>

<template>
  <div class="bubble" :class="msg.role === 'user' ? 'user' : 'assistant'">
    <div class="content">
      <span v-if="msg.loading && !msg.content" class="muted">思考中…</span>
      <template v-else>{{ msg.content }}</template>
    </div>
  </div>
</template>

<style scoped>
.bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.6;
}

.bubble.user {
  align-self: flex-end;
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.bubble.assistant {
  align-self: flex-start;
  background: #1f1f1f;
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}
</style>