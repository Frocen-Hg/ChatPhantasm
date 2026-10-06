<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useProvidersStore } from '../stores/providers'
import * as api from '../api/providers'
import type { ModelRoute, ProviderConfig } from '../types/provider'

const store = useProvidersStore()
const showForm = ref(false)
const editingId = ref<number | null>(null)
const name = ref('')
const type = ref('openai_compat')
const baseUrl = ref('')
const apiKey = ref('')
const modelsText = ref('')
const isDefault = ref(false)
const saving = ref(false)
const error = ref('')

const isEmbeddingDefault = ref(false)
const embeddingModel = ref('')

const testResult = ref<{ models?: string[]; error?: string } | null>(null)
const testing = ref(false)
const embeddingResult = ref<{ model?: string; dim?: number; error?: string } | null>(null)
const testingEmbedding = ref(false)

// ---- 功能位模型路由 ----
const CAPABILITIES = [
  { key: 'chat', label: '聊天', hint: '对话模型' },
  { key: 'embedding', label: '嵌入', hint: '向量化（记忆/知识库 RAG）' }
]

interface RouteForm {
  providerId: number | null
  model: string
  direct: boolean
  directName: string
  directType: string
  directBaseUrl: string
  directApiKey: string
}

function emptyRouteForm(): RouteForm {
  return {
    providerId: null,
    model: '',
    direct: false,
    directName: '',
    directType: 'openai_compat',
    directBaseUrl: '',
    directApiKey: ''
  }
}

const routes = ref<ModelRoute[]>([])
const routeForms = reactive<Record<string, RouteForm>>({})
for (const cap of CAPABILITIES) routeForms[cap.key] = emptyRouteForm()
const routeBusy = ref('')
const routeMsg = ref('')

onMounted(async () => {
  await store.fetchList()
  await loadRoutes()
})

async function loadRoutes(): Promise<void> {
  routes.value = await api.listRoutes()
  for (const cap of CAPABILITIES) {
    const r = routes.value.find((x) => x.capability === cap.key)
    const f = routeForms[cap.key]
    f.direct = false
    f.providerId = r?.provider_id ?? null
    f.model = r?.model ?? ''
  }
}

async function saveRoute(capability: string): Promise<void> {
  const f = routeForms[capability]
  routeBusy.value = capability
  routeMsg.value = ''
  try {
    let providerId = f.providerId
    if (f.direct) {
      if (!f.directBaseUrl) throw new Error('请填写 Base URL')
      const created = await store.create({
        name: f.directName || `direct-${capability}`,
        type: f.directType,
        base_url: f.directBaseUrl,
        api_key: f.directApiKey || null,
        models: f.model ? [f.model] : [],
        is_default: false,
        embedding_model: capability === 'embedding' ? f.model || null : null
      })
      providerId = created.id
    }
    if (!providerId) throw new Error('请选择 Provider 或开启 URL 直填')
    await api.setRoute(capability, { provider_id: providerId, model: f.model })
    routeMsg.value = `${capability} 已保存`
    await loadRoutes()
    await store.fetchList()
  } catch (e: any) {
    routeMsg.value = e?.message ?? String(e)
  } finally {
    routeBusy.value = ''
  }
}

async function clearRoute(capability: string): Promise<void> {
  await api.clearRoute(capability)
  routeMsg.value = `${capability} 已重置为默认`
  await loadRoutes()
}

async function testRoute(capability: string): Promise<void> {
  const r = routes.value.find((x) => x.capability === capability)
  if (!r) {
    routeMsg.value = '该功能位尚未绑定'
    return
  }
  routeBusy.value = capability
  routeMsg.value = ''
  try {
    const res = await api.testProvider({ id: r.provider_id, capability })
    if (!res.ok) {
      routeMsg.value = `测试失败：${res.error}`
    } else if (capability === 'embedding') {
      routeMsg.value = `嵌入连通：${res.model} · 维度 ${res.dim}`
    } else {
      routeMsg.value = `聊天连通，可用模型：${(res.models ?? []).join(', ') || '—'}`
    }
  } catch (e: any) {
    routeMsg.value = e?.message ?? String(e)
  } finally {
    routeBusy.value = ''
  }
}

function resetForm(): void {
  editingId.value = null
  name.value = ''
  type.value = 'openai_compat'
  baseUrl.value = type.value === 'ollama' ? 'http://localhost:11434' : ''
  apiKey.value = ''
  modelsText.value = ''
  isDefault.value = false
  isEmbeddingDefault.value = false
  embeddingModel.value = ''
}

function onTypeChange(): void {
  if (type.value === 'ollama' && !baseUrl.value) {
    baseUrl.value = 'http://localhost:11434'
  }
}

function openCreate(): void {
  resetForm()
  showForm.value = !showForm.value
}

function editProvider(p: ProviderConfig): void {
  editingId.value = p.id
  name.value = p.name
  type.value = p.type
  baseUrl.value = p.base_url
  apiKey.value = ''
  modelsText.value = p.models.join(',')
  isDefault.value = p.is_default
  isEmbeddingDefault.value = p.is_embedding_default
  embeddingModel.value = p.embedding_model ?? ''
  showForm.value = true
  error.value = ''
}

async function save(): Promise<void> {
  saving.value = true
  error.value = ''
  const payload = {
    name: name.value,
    type: type.value,
    base_url: baseUrl.value,
    api_key: apiKey.value || null,
    models: modelsText.value
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean),
    is_default: isDefault.value,
    embedding_model: embeddingModel.value || null,
    is_embedding_default: isEmbeddingDefault.value
  }
  try {
    if (editingId.value !== null) {
      await api.updateProvider(editingId.value, payload)
    } else {
      await store.create(payload)
    }
    showForm.value = false
    resetForm()
    await loadRoutes()
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    saving.value = false
  }
}

async function remove(id: number): Promise<void> {
  if (!confirm('确认删除该 Provider？')) return
  await store.remove(id)
  await loadRoutes()
}

async function test(id: number): Promise<void> {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = await api.testProvider({ id })
  } catch (e: any) {
    testResult.value = { error: e?.message ?? String(e) }
  } finally {
    testing.value = false
  }
}

async function testEmbed(id: number): Promise<void> {
  testingEmbedding.value = true
  embeddingResult.value = null
  try {
    embeddingResult.value = await api.testEmbedding({ id })
  } catch (e: any) {
    embeddingResult.value = { error: e?.message ?? String(e) }
  } finally {
    testingEmbedding.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="row header">
      <h2>模型 Provider 设置</h2>
      <button @click="openCreate">{{ showForm ? '取消' : '添加 Provider' }}</button>
    </div>

    <div class="panel matrix">
      <div class="row spread">
        <h3>功能位模型（不同功能用不同模型）</h3>
        <span class="muted">连接凭证与功能位解耦：一个 Provider 可被多个功能位复用</span>
      </div>

      <div v-for="cap in CAPABILITIES" :key="cap.key" class="route-row">
        <div class="row spread">
          <strong>{{ cap.label }}</strong>
          <span class="muted">{{ cap.key }} · {{ cap.hint }}</span>
        </div>

        <label class="check">
          <input v-model="routeForms[cap.key].direct" type="checkbox" /> URL 直填模式（不选 Provider，直接填地址）
        </label>

        <template v-if="!routeForms[cap.key].direct">
          <div class="field">
            <label>Provider</label>
            <select v-model="routeForms[cap.key].providerId">
              <option :value="null">（未选择）</option>
              <option v-for="p in store.list" :key="p.id" :value="p.id">
                {{ p.name }}（{{ p.type }}）
              </option>
            </select>
          </div>
        </template>
        <template v-else>
          <div class="field">
            <label>名称</label>
            <input v-model="routeForms[cap.key].directName" :placeholder="`direct-${cap.key}`" />
          </div>
          <div class="field">
            <label>类型</label>
            <select v-model="routeForms[cap.key].directType">
              <option value="openai_compat">openai_compat</option>
              <option value="ollama">ollama</option>
            </select>
          </div>
          <div class="field">
            <label>Base URL</label>
            <input v-model="routeForms[cap.key].directBaseUrl" placeholder="https://api.example.com" />
          </div>
          <div class="field">
            <label>API Key</label>
            <input v-model="routeForms[cap.key].directApiKey" type="password" />
          </div>
        </template>

        <div class="field">
          <label>模型</label>
          <input
            v-model="routeForms[cap.key].model"
            :placeholder="cap.key === 'embedding' ? 'nomic-embed-text' : 'deepseek-chat'"
          />
        </div>

        <div class="row actions">
          <button @click="saveRoute(cap.key)" :disabled="routeBusy === cap.key">
            {{ routeBusy === cap.key ? '保存中…' : '保存绑定' }}
          </button>
          <button class="ghost" @click="testRoute(cap.key)" :disabled="routeBusy === cap.key">测试</button>
          <button class="ghost" @click="clearRoute(cap.key)">重置为默认</button>
        </div>
      </div>

      <div v-if="routeMsg" class="muted">{{ routeMsg }}</div>
    </div>

    <form v-if="showForm" class="panel form" @submit.prevent="save">
      <div class="row">
        <h3>{{ editingId ? '编辑 Provider' : '添加 Provider' }}</h3>
        <span v-if="editingId" class="muted">API Key 留空表示不改动</span>
      </div>
      <div class="field">
        <label>名称</label>
        <input v-model="name" required placeholder="deepseek / ollama" />
      </div>
      <div class="field">
        <label>类型</label>
        <select v-model="type" @change="onTypeChange">
          <option value="openai_compat">openai_compat（外部 API）</option>
          <option value="ollama">ollama（本地）</option>
        </select>
      </div>
      <div class="field">
        <label>Base URL</label>
        <input v-model="baseUrl" placeholder="https://api.deepseek.com 或 http://localhost:11434" />
      </div>
      <div class="field">
        <label>API Key（ollama 可留空）</label>
        <input v-model="apiKey" type="password" />
      </div>
      <div class="field">
        <label>模型列表（逗号分隔）</label>
        <input v-model="modelsText" placeholder="deepseek-chat, deepseek-reasoner" />
      </div>
      <div class="field">
        <label>嵌入模型（独立于聊天模型，可留空用类型默认）</label>
        <input v-model="embeddingModel" placeholder="text-embedding-3-small 或 nomic-embed-text" />
      </div>
      <label class="check">
        <input v-model="isDefault" type="checkbox" /> 设为全局默认（聊天）
      </label>
      <label class="check">
        <input v-model="isEmbeddingDefault" type="checkbox" /> 设为嵌入默认
      </label>
      <div class="row">
        <button type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存' }}</button>
      </div>
    </form>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="list">
      <div v-for="p in store.list" :key="p.id" class="panel item">
        <div class="row spread">
          <strong>
            {{ p.name }}
            <span v-if="p.is_default" class="tag">默认</span>
            <span v-if="p.is_embedding_default" class="tag tag-embed">嵌入</span>
          </strong>
          <span class="muted">{{ p.type }}</span>
        </div>
        <div class="muted">base_url: {{ p.base_url || '（默认）' }}</div>
        <div class="muted">models: {{ p.models.join(', ') || '—' }}</div>
        <div class="muted">embedding: {{ p.embedding_model || '（类型默认）' }}</div>
        <div v-if="p.api_key_masked" class="muted">api_key: {{ p.api_key_masked }}</div>
        <div class="row actions">
          <button class="ghost" @click="editProvider(p)">编辑</button>
          <button class="ghost" @click="test(p.id)" :disabled="testing">测试连通</button>
          <button class="ghost" @click="testEmbed(p.id)" :disabled="testingEmbedding">测试嵌入</button>
          <button class="danger" @click="remove(p.id)">删除</button>
        </div>
      </div>
    </div>

    <div v-if="testResult" class="panel result">
      <template v-if="testResult.error">
        <div class="error">测试失败：{{ testResult.error }}</div>
      </template>
      <template v-else>
        <div class="ok">连通成功，可用模型：{{ testResult.models?.join(', ') || '—' }}</div>
      </template>
    </div>

    <div v-if="embeddingResult" class="panel result">
      <template v-if="embeddingResult.error">
        <div class="error">嵌入测试失败：{{ embeddingResult.error }}</div>
      </template>
      <template v-else>
        <div class="ok">
          嵌入连通成功：{{ embeddingResult.model }} · 维度 {{ embeddingResult.dim }}
        </div>
      </template>
    </div>
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
  max-width: 560px;
  margin-bottom: 16px;
}

.matrix {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 640px;
  margin-bottom: 16px;
}

.route-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

label {
  font-size: 13px;
  color: var(--muted);
}

.check {
  display: flex;
  gap: 6px;
  align-items: center;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 560px;
}

.item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.spread {
  justify-content: space-between;
}

.tag {
  background: rgba(139, 92, 246, 0.2);
  color: var(--accent);
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
}

.tag-embed {
  background: rgba(56, 189, 248, 0.2);
  color: #38bdf8;
}

.actions {
  margin-top: 6px;
}

.result {
  margin-top: 16px;
  max-width: 560px;
}

.ok {
  color: #4ade80;
}

.error {
  color: #f87171;
}
</style>
