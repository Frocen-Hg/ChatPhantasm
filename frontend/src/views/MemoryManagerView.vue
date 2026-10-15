<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useCharactersStore } from '../stores/characters'
import * as api from '../api/memory'
import type {
  CharacterState,
  ContextPreview,
  Memory,
  MemorySearchResult
} from '../types/memory'

const characters = useCharactersStore()

const characterId = ref<number | null>(null)
const memories = ref<Memory[]>([])
const state = ref<CharacterState | null>(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const decaying = ref(false)

const searchQuery = ref('')
const searchTopK = ref(6)
const searchResults = ref<MemorySearchResult[]>([])
const searchLoading = ref(false)
const searching = ref(false)
const preview = ref<ContextPreview | null>(null)

const editingState = ref(false)
const stateMood = ref('')
const stateArousal = ref(0)
const stateFocus = ref('')
const stateRelationship = ref('{}')
const savingState = ref(false)

const layerFilter = ref('')
const kindFilter = ref('')
const keyword = ref('')

const showForm = ref(false)
const formContent = ref('')
const formKind = ref('fact')
const formLayer = ref('L3')
const formImportance = ref(5)
const formVisibility = ref('public')
const saving = ref(false)

const editingId = ref<number | null>(null)
const editContent = ref('')
const editImportance = ref(5)
const editVisibility = ref('public')

const KIND_OPTIONS = [
  { value: 'fact', label: '事实' },
  { value: 'preference', label: '偏好' },
  { value: 'relation', label: '关系' },
  { value: 'summary', label: '摘要' },
  { value: 'monologue', label: '独白' },
  { value: 'reflection', label: '反思' }
]
const LAYER_OPTIONS = [
  { value: 'L2', label: 'L2 情节' },
  { value: 'L3', label: 'L3 长期' },
  { value: 'L4', label: 'L4 内心' }
]

const KIND_LABELS: Record<string, string> = {
  summary: '摘要',
  fact: '事实',
  preference: '偏好',
  relation: '关系',
  episode: '情节',
  monologue: '独白',
  reflection: '反思'
}

onMounted(async () => {
  await characters.fetchList()
  if (characters.list.length) {
    characterId.value = characters.list[0].id
    await load()
  }
})

async function load(): Promise<void> {
  if (!characterId.value) return
  loading.value = true
  error.value = ''
  try {
    const [list, st] = await Promise.all([
      api.listMemories(characterId.value, {
        layer: layerFilter.value || undefined,
        kind: kindFilter.value || undefined
      }),
      api.getCharacterState(characterId.value)
    ])
    memories.value = list
    state.value = st
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    loading.value = false
  }
}

async function onCharacterChange(): Promise<void> {
  editingId.value = null
  showForm.value = false
  editingState.value = false
  await load()
}

function startEditState(): void {
  if (!state.value) return
  editingState.value = true
  stateMood.value = state.value.mood
  stateArousal.value = state.value.arousal
  stateFocus.value = state.value.current_focus
  stateRelationship.value = JSON.stringify(state.value.relationship)
}

async function saveState(): Promise<void> {
  if (!characterId.value) return
  savingState.value = true
  error.value = ''
  try {
    let relationship: Record<string, unknown> = {}
    if (stateRelationship.value.trim()) relationship = JSON.parse(stateRelationship.value)
    await api.updateCharacterState(characterId.value, {
      mood: stateMood.value,
      arousal: stateArousal.value,
      current_focus: stateFocus.value,
      relationship
    })
    editingState.value = false
    await load()
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    savingState.value = false
  }
}

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return memories.value
  return memories.value.filter((m) => m.content.toLowerCase().includes(kw))
})

function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind
}

async function create(): Promise<void> {
  if (!characterId.value || !formContent.value.trim()) return
  saving.value = true
  error.value = ''
  try {
    await api.createMemory(characterId.value, {
      content: formContent.value.trim(),
      kind: formKind.value,
      layer: formLayer.value,
      importance: formImportance.value,
      visibility: formVisibility.value
    })
    formContent.value = ''
    formImportance.value = 5
    showForm.value = false
    await load()
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    saving.value = false
  }
}

function startEdit(m: Memory): void {
  editingId.value = m.id
  editContent.value = m.content
  editImportance.value = m.importance
  editVisibility.value = m.visibility
}

async function saveEdit(id: number): Promise<void> {
  error.value = ''
  try {
    await api.updateMemory(id, {
      content: editContent.value,
      importance: editImportance.value,
      visibility: editVisibility.value
    })
    editingId.value = null
    await load()
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  }
}

async function remove(id: number): Promise<void> {
  if (!confirm('确认删除该记忆？')) return
  await api.deleteMemory(id)
  await load()
}

async function search(): Promise<void> {
  if (!characterId.value || !searchQuery.value.trim()) return
  searching.value = true
  error.value = ''
  try {
    const res = await api.searchMemories(characterId.value, searchQuery.value.trim(), searchTopK.value)
    searchResults.value = res.results
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    searching.value = false
  }
}

async function loadPreview(): Promise<void> {
  if (!characterId.value) return
  searchLoading.value = true
  error.value = ''
  try {
    preview.value = await api.previewContext(characterId.value, searchQuery.value.trim())
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    searchLoading.value = false
  }
}

async function decay(): Promise<void> {
  if (!characterId.value) return
  decaying.value = true
  error.value = ''
  notice.value = ''
  try {
    const res = await api.decayMemories(characterId.value)
    notice.value = `已归档 ${res.archived} 条衰减记忆`
    await load()
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    decaying.value = false
  }
}

function fmt(dt: string | null): string {
  if (!dt) return '—'
  return new Date(dt).toLocaleString()
}
</script>

<template>
  <div class="page">
    <div class="row header">
      <h2>记忆管理</h2>
      <div class="row">
        <select v-model.number="characterId" @change="onCharacterChange">
          <option v-for="c in characters.list" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
        <button class="ghost" @click="load">刷新</button>
        <button class="ghost" :disabled="decaying" @click="decay">
          {{ decaying ? '清理中…' : '清理衰减' }}
        </button>
        <button @click="showForm = !showForm">{{ showForm ? '取消' : '新建记忆' }}</button>
      </div>
    </div>

    <div v-if="notice" class="notice">{{ notice }}</div>

    <div v-if="state" class="panel state">
      <div class="row spread">
        <strong>内心状态</strong>
        <button v-if="!editingState" class="ghost" @click="startEditState">编辑</button>
      </div>

      <template v-if="editingState">
        <div class="row wrap">
          <div class="field grow">
            <label>心情</label>
            <input v-model="stateMood" placeholder="如：好奇、低落" />
          </div>
          <div class="field grow">
            <label>当前关注</label>
            <input v-model="stateFocus" placeholder="如：用户提到的旅行计划" />
          </div>
          <div class="field grow">
            <label>唤醒度</label>
            <input v-model.number="stateArousal" type="number" step="0.1" />
          </div>
        </div>
        <div class="field">
          <label>关系状态（JSON）</label>
          <textarea v-model="stateRelationship" rows="2" placeholder='{"用户": {"亲密度": 0.6}}' />
        </div>
        <div class="row">
          <button :disabled="savingState" @click="saveState">
            {{ savingState ? '保存中…' : '保存' }}
          </button>
          <button class="ghost" @click="editingState = false">取消</button>
        </div>
      </template>

      <template v-else>
        <div class="muted">
          心情：{{ state.mood || '—' }} · 关注：{{ state.current_focus || '—' }} · 唤醒：{{ state.arousal }}
        </div>
        <div class="muted">上次交互：{{ fmt(state.last_user_at) }} · 上次心跳：{{ fmt(state.last_beat_at) }}</div>
        <div v-if="Object.keys(state.relationship).length" class="muted">
          关系：{{ JSON.stringify(state.relationship) }}
        </div>
      </template>
    </div>

    <div class="panel preview">
      <div class="row spread">
        <strong>检索预览</strong>
        <button class="ghost" :disabled="searchLoading" @click="loadPreview">
          {{ searchLoading ? '组装中…' : '上下文预览' }}
        </button>
      </div>
      <div class="row wrap">
        <div class="field grow">
          <label>query（用于关键词检索）</label>
          <input v-model="searchQuery" placeholder="输入要检索的内容" @keyup.enter="search" />
        </div>
        <div class="field" style="width: 100px">
          <label>top_k</label>
          <input v-model.number="searchTopK" type="number" min="1" max="20" />
        </div>
        <button :disabled="searching || !searchQuery.trim()" @click="search">
          {{ searching ? '检索中…' : '检索' }}
        </button>
      </div>

      <div v-if="searchResults.length" class="search-list">
        <div v-for="(r, i) in searchResults" :key="r.id" class="search-item">
          <div class="row spread">
            <span>
              <span class="tag">{{ r.layer }}</span>
              <span class="tag tag-kind">{{ kindLabel(r.kind) }}</span>
              <span class="muted"> #{{ r.id }}</span>
            </span>
            <span class="muted">
              score {{ r.score }} · 关键词 {{ r.keyword }} · 向量 {{ r.vector ?? '—' }} · 新近
              {{ r.recency }} · {{ r.tokens }} tok
            </span>
          </div>
          <p class="content">{{ r.content }}</p>
        </div>
      </div>
      <div v-else-if="searchQuery && !searching" class="muted">无命中（或尚未检索）</div>

      <template v-if="preview">
        <div class="muted">
          预算 {{ preview.budget }} · 已用 {{ preview.total_tokens }}（含历史
          {{ preview.history.length }} 条）
        </div>
        <details v-for="b in preview.blocks" :key="b.name" class="block-item">
          <summary>[{{ b.name }}] {{ b.tokens }} tok</summary>
          <pre class="block-content">{{ b.content }}</pre>
        </details>
      </template>
    </div>

    <form v-if="showForm" class="panel form" @submit.prevent="create">
      <div class="field">
        <label>内容</label>
        <textarea v-model="formContent" rows="3" required placeholder="要写入长期记忆的内容" />
      </div>
      <div class="row wrap">
        <div class="field grow">
          <label>类型</label>
          <select v-model="formKind">
            <option v-for="k in KIND_OPTIONS" :key="k.value" :value="k.value">{{ k.label }}</option>
          </select>
        </div>
        <div class="field grow">
          <label>层级</label>
          <select v-model="formLayer">
            <option v-for="l in LAYER_OPTIONS" :key="l.value" :value="l.value">{{ l.label }}</option>
          </select>
        </div>
        <div class="field grow">
          <label>重要度（1-10）</label>
          <input v-model.number="formImportance" type="number" min="1" max="10" />
        </div>
        <div class="field grow">
          <label>可见性</label>
          <select v-model="formVisibility">
            <option value="public">public（参与对话注入）</option>
            <option value="private">private（仅内心/独白）</option>
          </select>
        </div>
      </div>
      <div class="row">
        <button type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存' }}</button>
      </div>
    </form>

    <div class="panel filters">
      <div class="row wrap">
        <div class="field grow">
          <label>层级</label>
          <select v-model="layerFilter" @change="load">
            <option value="">全部</option>
            <option v-for="l in LAYER_OPTIONS" :key="l.value" :value="l.value">{{ l.label }}</option>
          </select>
        </div>
        <div class="field grow">
          <label>类型</label>
          <select v-model="kindFilter" @change="load">
            <option value="">全部</option>
            <option v-for="k in KIND_OPTIONS" :key="k.value" :value="k.value">{{ k.label }}</option>
          </select>
        </div>
        <div class="field grow">
          <label>关键词（本地过滤）</label>
          <input v-model="keyword" placeholder="搜索记忆内容" />
        </div>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="loading" class="muted">加载中…</div>
    <div v-else-if="!filtered.length" class="muted">暂无记忆</div>

    <div class="list">
      <div v-for="m in filtered" :key="m.id" class="panel item">
        <div class="row spread">
          <div class="row">
            <span class="tag">{{ m.layer }}</span>
            <span class="tag tag-kind">{{ kindLabel(m.kind) }}</span>
            <span v-if="m.visibility === 'private'" class="tag tag-private">private</span>
            <span v-if="m.decay_at" class="tag tag-archived">已归档</span>
          </div>
          <span class="muted">
            #{{ m.id }}
            <template v-if="m.source_start_id">· 溯源 #{{ m.source_start_id }}-{{ m.source_end_id }}</template>
            · {{ fmt(m.created_at) }}
          </span>
        </div>

        <template v-if="editingId === m.id">
          <textarea v-model="editContent" rows="3" />
          <div class="row wrap">
            <div class="field grow">
              <label>重要度</label>
              <input v-model.number="editImportance" type="number" min="1" max="10" />
            </div>
            <div class="field grow">
              <label>可见性</label>
              <select v-model="editVisibility">
                <option value="public">public</option>
                <option value="private">private</option>
              </select>
            </div>
          </div>
          <div class="row actions">
            <button @click="saveEdit(m.id)">保存</button>
            <button class="ghost" @click="editingId = null">取消</button>
          </div>
        </template>

        <template v-else>
          <p class="content" :class="{ archived: !!m.decay_at }">{{ m.content }}</p>
          <div class="row spread">
            <span class="muted">重要度 {{ m.importance }} · 访问 {{ m.access_count }} 次</span>
            <div class="row actions">
              <button class="ghost" @click="startEdit(m)">编辑</button>
              <button class="danger" @click="remove(m.id)">删除</button>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 16px;
  overflow-y: auto;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.header {
  justify-content: space-between;
}

.header select {
  width: 160px;
}

.state,
.form,
.filters,
.preview {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 720px;
}

.search-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.search-item {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 8px;
}

.block-item {
  font-size: 13px;
}

.block-content {
  white-space: pre-wrap;
  word-break: break-word;
  background: rgba(0, 0, 0, 0.25);
  border-radius: 8px;
  padding: 8px;
  margin: 6px 0 0;
  max-height: 240px;
  overflow-y: auto;
  font-size: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field.grow {
  flex: 1;
  min-width: 140px;
}

label {
  font-size: 13px;
  color: var(--muted);
}

.wrap {
  flex-wrap: wrap;
  align-items: flex-end;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 720px;
}

.item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.spread {
  justify-content: space-between;
}

.content {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.5;
}

.tag {
  background: rgba(139, 92, 246, 0.2);
  color: var(--accent);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
}

.tag-kind {
  background: rgba(56, 189, 248, 0.2);
  color: #38bdf8;
}

.tag-private {
  background: rgba(248, 113, 113, 0.2);
  color: #f87171;
}

.tag-archived {
  background: rgba(156, 163, 175, 0.2);
  color: #9ca3af;
}

.content.archived {
  opacity: 0.5;
  text-decoration: line-through;
}

.notice {
  color: #4ade80;
  font-size: 13px;
}

.actions {
  margin-top: 0;
}

.error {
  color: #f87171;
  max-width: 720px;
}
</style>
