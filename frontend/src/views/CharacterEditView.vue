<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useCharactersStore } from '../stores/characters'
import { useProvidersStore } from '../stores/providers'
import { emptyCard, type CharacterCard, type CharacterExt } from '../types/character'

const props = defineProps<{ id?: string }>()
const router = useRouter()
const characters = useCharactersStore()
const providers = useProvidersStore()

const card = ref<CharacterCard>(emptyCard())
const ext = ref<CharacterExt>({})
const tagsText = ref('')
const saving = ref(false)
const error = ref('')
const saved = ref(false)

const isNew = computed(() => !props.id)
const modelProvider = computed({
  get: () => ext.value.model?.provider ?? null,
  set: (v: number | null) => {
    ext.value.model = { ...(ext.value.model ?? {}), provider: v }
  }
})
const modelName = computed({
  get: () => ext.value.model?.model ?? '',
  set: (v: string) => {
    ext.value.model = { ...(ext.value.model ?? {}), model: v }
  }
})
const temperature = computed({
  get: () => ext.value.model?.temperature ?? 1.3,
  set: (v: number) => {
    ext.value.model = { ...(ext.value.model ?? {}), temperature: v }
  }
})

onMounted(async () => {
  await providers.fetchList()
  if (!isNew.value && props.id) {
    const c = await characters.get(Number(props.id))
    card.value = c.card
    ext.value = c.ext
    tagsText.value = (c.card.tags ?? []).join(',')
  }
})

async function save(): Promise<void> {
  saving.value = true
  saved.value = false
  error.value = ''
  try {
    card.value.tags = tagsText.value
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
    if (isNew.value) {
      const c = await characters.create(card.value, ext.value)
      router.replace(`/characters/${c.id}`)
    } else {
      await characters.update(Number(props.id), card.value, ext.value)
    }
    saved.value = true
    setTimeout(() => (saved.value = false), 2000)
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="row header">
      <h2>{{ isNew ? '新建角色' : `编辑 ${card.name}` }}</h2>
      <div class="row">
        <span v-if="saved" class="muted ok">已保存</span>
        <button class="ghost" @click="router.push('/characters')">返回</button>
        <button @click="save" :disabled="saving">{{ saving ? '保存中…' : '保存' }}</button>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <form class="panel form" @submit.prevent="save">
      <div class="field">
        <label>名称</label>
        <input v-model="card.name" required />
      </div>

      <div class="field">
        <label>标签（逗号分隔）</label>
        <input v-model="tagsText" />
      </div>

      <div class="field">
        <label>简介 description</label>
        <textarea v-model="card.description" rows="2"></textarea>
      </div>

      <div class="field">
        <label>性格 personality</label>
        <textarea v-model="card.personality" rows="3"></textarea>
      </div>

      <div class="field">
        <label>场景 scenario</label>
        <textarea v-model="card.scenario" rows="3"></textarea>
      </div>

      <div class="field">
        <label>开场白 first_mes</label>
        <textarea v-model="card.first_mes" rows="3"></textarea>
      </div>

      <div class="field">
        <label>系统提示词 system_prompt（留空则按字段拼装）</label>
        <textarea v-model="card.system_prompt" rows="8"></textarea>
      </div>

      <details class="field">
        <summary>模型配置（ext.model，可覆盖全局默认）</summary>
        <div class="subgrid">
          <label>Provider
            <select v-model.number="modelProvider">
              <option :value="null">（使用全局默认）</option>
              <option v-for="p in providers.list" :key="p.id" :value="p.id">{{ p.name }} ({{ p.type }})</option>
            </select>
          </label>
          <label>模型名
            <input v-model="modelName" placeholder="deepseek-chat" />
          </label>
          <label>temperature
            <input v-model.number="temperature" type="number" step="0.1" min="0" max="2" />
          </label>
        </div>
      </details>
    </form>
  </div>
</template>

<style scoped>
.page {
  padding: 16px;
  overflow-y: auto;
  height: 100%;
}

.header {
  justify-content: space-between;
  margin-bottom: 16px;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 720px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field summary {
  cursor: pointer;
  color: var(--accent);
}

.subgrid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--muted);
}

.ok {
  color: #4ade80;
}

.error {
  color: #f87171;
  margin-bottom: 8px;
}
</style>