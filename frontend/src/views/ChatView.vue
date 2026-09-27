<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useCharactersStore } from '../stores/characters'
import { streamChat } from '../api/chat'
import {
  deleteConversation,
  getMessages,
  listConversations,
  type Conversation
} from '../api/conversations'
import MessageBubble from '../components/MessageBubble.vue'

interface Msg {
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
}

const characters = useCharactersStore()
const currentId = ref<number | null>(null)
const conversations = ref<Conversation[]>([])
const activeConvId = ref<number | null>(null)
const messages = ref<Msg[]>([])
const input = ref('')
const sending = ref(false)
const error = ref('')
const msgsEl = ref<HTMLElement | null>(null)

const currentCharacter = computed(() => characters.list.find((c) => c.id === currentId.value))

onMounted(async () => {
  await characters.fetchList()
  if (characters.list.length) {
    currentId.value = characters.list[0].id
  }
})

watch(currentId, async (id) => {
  if (id === null) return
  activeConvId.value = null
  messages.value = []
  error.value = ''
  await loadConversations()
})

async function loadConversations(): Promise<void> {
  if (currentId.value === null) return
  try {
    conversations.value = await listConversations(currentId.value)
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  }
}

async function openConversation(id: number): Promise<void> {
  if (sending.value) return
  activeConvId.value = id
  messages.value = []
  error.value = ''
  try {
    const msgs = await getMessages(id)
    messages.value = msgs.map((m) => ({
      role: (m.role === 'user' ? 'user' : 'assistant') as 'user' | 'assistant',
      content: m.content
    }))
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  }
}

function newChat(): void {
  if (sending.value) return
  activeConvId.value = null
  messages.value = []
  error.value = ''
}

async function removeConversation(id: number): Promise<void> {
  if (!confirm('确认删除该会话及其全部消息？')) return
  try {
    await deleteConversation(id)
    if (activeConvId.value === id) newChat()
    await loadConversations()
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  }
}

async function send(): Promise<void> {
  const text = input.value.trim()
  if (!text || sending.value || currentId.value === null) return
  input.value = ''
  error.value = ''

  messages.value.push({ role: 'user', content: text })
  const assistant = reactive<Msg>({ role: 'assistant', content: '', loading: true })
  messages.value.push(assistant)
  sending.value = true

  try {
    const convId = await streamChat(
      { character_id: currentId.value, conversation_id: activeConvId.value, content: text },
      (token) => {
        assistant.content += token
      }
    )
    if (convId !== null) activeConvId.value = convId
    await loadConversations()
  } catch (e: any) {
    error.value = e?.message ?? String(e)
    assistant.content = ''
    assistant.loading = false
  } finally {
    assistant.loading = false
    sending.value = false
  }
}

watch(
  () => messages.value.length,
  () => {
    if (msgsEl.value) msgsEl.value.scrollTop = msgsEl.value.scrollHeight
  }
)
</script>

<template>
  <div class="chat">
    <aside class="convs">
      <div class="convs-head">
        <button class="ghost full" @click="newChat">＋ 新对话</button>
      </div>
      <div class="convs-list">
        <div
          v-for="c in conversations"
          :key="c.id"
          class="conv-item"
          :class="{ active: c.id === activeConvId }"
          @click="openConversation(c.id)"
        >
          <div class="conv-title">{{ c.title }}</div>
          <div class="conv-preview">{{ c.last_message || '（空会话）' }}</div>
          <div class="row conv-meta">
            <span class="muted">{{ c.message_count }} 条</span>
            <button class="ghost small danger-text" @click.stop="removeConversation(c.id)">删除</button>
          </div>
        </div>
        <div v-if="!conversations.length" class="muted empty">暂无历史会话</div>
      </div>
    </aside>

    <div class="main">
      <header class="panel chat-header">
        <div class="row">
          <select v-model.number="currentId">
            <option v-for="c in characters.list" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <span class="muted">{{ activeConvId ? `会话 #${activeConvId}` : '新对话' }}</span>
        </div>
        <span v-if="currentCharacter" class="muted">{{ currentCharacter.card.description }}</span>
      </header>

      <main ref="msgsEl" class="messages">
        <MessageBubble v-for="(m, i) in messages" :key="i" :msg="m" />
        <div v-if="error" class="error">{{ error }}</div>
      </main>

      <footer class="panel input-area">
        <input
          v-model="input"
          placeholder="说点什么…"
          @keyup.enter="send"
          :disabled="sending"
        />
        <button @click="send" :disabled="sending">发送</button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.chat {
  display: flex;
  height: 100%;
}

.convs {
  width: 240px;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.convs-head {
  padding: 12px;
  border-bottom: 1px solid var(--border);
}

.convs-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.conv-item {
  background: rgba(30, 30, 30, 0.7);
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.conv-item:hover {
  border-color: var(--border);
}

.conv-item.active {
  border-color: var(--accent);
  background: rgba(139, 92, 246, 0.15);
}

.conv-title {
  font-size: 13px;
  font-weight: 600;
}

.conv-preview {
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-meta {
  justify-content: space-between;
}

.empty {
  padding: 16px;
  text-align: center;
}

.full {
  width: 100%;
}

.small {
  padding: 2px 8px;
  font-size: 12px;
}

.danger-text {
  color: #f87171;
  border-color: rgba(248, 113, 113, 0.4);
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  border-radius: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-header select {
  max-width: 240px;
}

.messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}

.input-area {
  display: flex;
  gap: 8px;
  border-radius: 0;
}

.error {
  color: #f87171;
  font-size: 13px;
  padding: 4px;
}
</style>