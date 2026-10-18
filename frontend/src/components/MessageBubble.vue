<script setup lang="ts">
defineProps<{
  msg: {
    role: 'user' | 'assistant'
    content: string
    loading?: boolean
    heartbeat?: 'proactive' | 'monologue'
  }
}>()
</script>

<template>
  <div
    class="bubble"
    :class="[msg.role === 'user' ? 'user' : 'assistant', msg.heartbeat ? `hb-${msg.heartbeat}` : '']"
  >
    <div v-if="msg.heartbeat" class="badge">
      {{ msg.heartbeat === 'proactive' ? '主动开口' : '内心独白' }}
    </div>
    <div class="content">
      <span v-if="msg.loading && !msg.content" class="muted">角色在思考…</span>
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

.bubble.hb-proactive {
  border-color: rgba(74, 222, 128, 0.5);
  background: rgba(74, 222, 128, 0.08);
}

.bubble.hb-monologue {
  border: 1px dashed rgba(148, 163, 184, 0.6);
  background: rgba(148, 163, 184, 0.08);
  color: var(--muted);
  font-style: italic;
}

.badge {
  font-size: 11px;
  color: var(--muted);
  margin-bottom: 4px;
}

.hb-proactive .badge {
  color: #4ade80;
}

.content {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
