<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useCharactersStore } from '../stores/characters'
import { streamChat } from '../api/chat'
import MessageBubble from '../components/MessageBubble.vue'

interface Msg {
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
}

const characters = useCharactersStore()
const currentId = ref<number | null>(null)
const conversationId = ref<number | null>(null)
const messages = ref<Msg[]>([])
const input = ref('')
const sending = ref(false)
const error = ref('')

const currentCharacter = computed(() => characters.list.find((c) => c.id === currentId.value))

onMounted(async () => {
  await characters.fetchList()
  if (characters.list.length) {
    currentId.value = characters.list[0].id
  }
})

function newChat(): void {
  conversationId.value = null
  messages.value = []
  error.value = ''
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
      { character_id: currentId.value, conversation_id: conversationId.value, content: text },
      (token) => {
        assistant.content += token
      }
    )
    if (convId !== null) conversationId.value = convId
  } catch (e: any) {
    error.value = e?.message ?? String(e)
    assistant.content = ''
    assistant.loading = false
  } finally {
    assistant.loading = false
    sending.value = false
  }
}
</script>

<template>
  <div class="chat">
    <header class="panel chat-header">
      <div class="row">
        <select v-model.number="currentId">
          <option v-for="c in characters.list" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
        <button class="ghost" @click="newChat">新对话</button>
      </div>
      <span v-if="currentCharacter" class="muted">{{ currentCharacter.card.description }}</span>
    </header>

    <main class="messages">
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
</template>

<style scoped>
.chat {
  display: flex;
  flex-direction: column;
  height: 100%;
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