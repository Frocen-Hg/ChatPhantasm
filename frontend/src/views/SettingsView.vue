<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useProvidersStore } from '../stores/providers'
import * as api from '../api/providers'
import type { ProviderConfig } from '../types/provider'

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

const testResult = ref<{ models?: string[]; error?: string } | null>(null)
const testing = ref(false)

onMounted(() => store.fetchList())

function resetForm(): void {
  editingId.value = null
  name.value = ''
  type.value = 'openai_compat'
  baseUrl.value = type.value === 'ollama' ? 'http://localhost:11434' : ''
  apiKey.value = ''
  modelsText.value = ''
  isDefault.value = false
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
    is_default: isDefault.value
  }
  try {
    if (editingId.value !== null) {
      await api.updateProvider(editingId.value, payload)
    } else {
      await store.create(payload)
    }
    showForm.value = false
    resetForm()
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    saving.value = false
  }
}

async function remove(id: number): Promise<void> {
  if (!confirm('确认删除该 Provider？')) return
  await store.remove(id)
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
</script>

<template>
  <div class="page">
    <div class="row header">
      <h2>模型 Provider 设置</h2>
      <button @click="openCreate">{{ showForm ? '取消' : '添加 Provider' }}</button>
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
      <label class="check">
        <input v-model="isDefault" type="checkbox" /> 设为全局默认
      </label>
      <div class="row">
        <button type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存' }}</button>
      </div>
    </form>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="list">
      <div v-for="p in store.list" :key="p.id" class="panel item">
        <div class="row spread">
          <strong>{{ p.name }} <span v-if="p.is_default" class="tag">默认</span></strong>
          <span class="muted">{{ p.type }}</span>
        </div>
        <div class="muted">base_url: {{ p.base_url || '（默认）' }}</div>
        <div class="muted">models: {{ p.models.join(', ') || '—' }}</div>
        <div v-if="p.api_key_masked" class="muted">api_key: {{ p.api_key_masked }}</div>
        <div class="row actions">
          <button class="ghost" @click="editProvider(p)">编辑</button>
          <button class="ghost" @click="test(p.id)" :disabled="testing">测试连通</button>
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