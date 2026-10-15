<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useCharactersStore } from '../stores/characters'
import * as api from '../api/kb'
import type { KbChunk, KbDocument, KbLore, KbSearchResult } from '../types/kb'

const props = defineProps<{ id: string }>()
const router = useRouter()
const characters = useCharactersStore()

const characterId = computed(() => Number(props.id))
const character = computed(
  () => characters.list.find((c) => c.id === characterId.value) ?? null
)

const documents = ref<KbDocument[]>([])
const lores = ref<KbLore[]>([])
const chunksMap = reactive<Record<number, KbChunk[] | null>>({})
const error = ref('')
const notice = ref('')
const busy = ref('')

const docTitle = ref('')
const docText = ref('')
const docScope = ref('world')
const docVisibility = ref('public')
const fileInput = ref<HTMLInputElement | null>(null)

const editingLoreId = ref<number | null>(null)
const loreContent = ref('')
const loreKeys = ref('')
const loreConstant = ref(false)
const lorePriority = ref(0)
const loreScanDepth = ref(6)
const loreEnabled = ref(true)

const searchQuery = ref('')
const searchResult = ref<KbSearchResult | null>(null)

onMounted(async () => {
  if (!characters.list.length) await characters.fetchList()
  await loadAll()
})

async function loadAll(): Promise<void> {
  await run('load', async () => {
    await Promise.all([loadDocuments(), loadLore()])
  })
}

async function loadDocuments(): Promise<void> {
  documents.value = await api.listDocuments(characterId.value)
}

async function loadLore(): Promise<void> {
  lores.value = await api.listLore(characterId.value)
}

function flash(message: string): void {
  notice.value = message
  window.setTimeout(() => {
    if (notice.value === message) notice.value = ''
  }, 3000)
}

async function run(label: string, fn: () => Promise<void>): Promise<void> {
  busy.value = label
  error.value = ''
  try {
    await fn()
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    busy.value = ''
  }
}

async function importText(): Promise<void> {
  if (!docText.value.trim()) return
  await run('import', async () => {
    const doc = await api.createDocument(characterId.value, {
      title: docTitle.value || '未命名文档',
      text: docText.value,
      scope: docScope.value,
      visibility: docVisibility.value
    })
    docText.value = ''
    docTitle.value = ''
    await loadDocuments()
    flash(`已导入「${doc.title}」：${doc.chunk_count} 块，索引中…`)
    window.setTimeout(loadDocuments, 3000)
  })
}

async function onFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  await run('upload', async () => {
    const doc = await api.uploadDocument(
      characterId.value,
      file,
      docScope.value,
      docVisibility.value
    )
    await loadDocuments()
    flash(`已上传「${doc.title}」：${doc.chunk_count} 块，索引中…`)
    window.setTimeout(loadDocuments, 3000)
  })
}

async function toggleChunks(doc: KbDocument): Promise<void> {
  if (chunksMap[doc.id]) {
    chunksMap[doc.id] = null
    return
  }
  await run('chunks', async () => {
    chunksMap[doc.id] = await api.listChunks(doc.id)
  })
}

async function reindex(doc: KbDocument): Promise<void> {
  await run('reindex', async () => {
    await api.reindexDocument(doc.id)
    chunksMap[doc.id] = null
    await loadDocuments()
    flash('已重新入队索引')
    window.setTimeout(loadDocuments, 3000)
  })
}

async function removeDoc(doc: KbDocument): Promise<void> {
  if (!confirm(`确认删除文档「${doc.title}」？`)) return
  await run('delete', async () => {
    await api.deleteDocument(doc.id)
    delete chunksMap[doc.id]
    await loadDocuments()
  })
}

function resetLoreForm(): void {
  editingLoreId.value = null
  loreContent.value = ''
  loreKeys.value = ''
  loreConstant.value = false
  lorePriority.value = 0
  loreScanDepth.value = 6
  loreEnabled.value = true
}

function editLore(lore: KbLore): void {
  editingLoreId.value = lore.id
  loreContent.value = lore.content
  loreKeys.value = lore.keys.join(',')
  loreConstant.value = lore.constant
  lorePriority.value = lore.priority
  loreScanDepth.value = lore.scan_depth
  loreEnabled.value = lore.enabled
}

async function saveLore(): Promise<void> {
  if (!loreContent.value.trim()) return
  await run('lore', async () => {
    const payload = {
      content: loreContent.value.trim(),
      keys: loreKeys.value
        .split(/[,，]/)
        .map((s) => s.trim())
        .filter(Boolean),
      constant: loreConstant.value,
      priority: lorePriority.value,
      scan_depth: loreScanDepth.value,
      enabled: loreEnabled.value
    }
    if (editingLoreId.value !== null) await api.updateLore(editingLoreId.value, payload)
    else await api.createLore(characterId.value, payload)
    resetLoreForm()
    await loadLore()
  })
}

async function removeLore(lore: KbLore): Promise<void> {
  if (!confirm('确认删除该 lore 条目？')) return
  await run('lore-del', async () => {
    await api.deleteLore(lore.id)
    if (editingLoreId.value === lore.id) resetLoreForm()
    await loadLore()
  })
}

async function search(): Promise<void> {
  if (!searchQuery.value.trim()) return
  await run('search', async () => {
    searchResult.value = await api.searchKnowledge(characterId.value, searchQuery.value.trim())
  })
}

function goBack(): void {
  if (window.history.length > 1) router.back()
  else router.push('/characters')
}
</script>

<template>
  <div class="kb-page">
    <header class="kb-header">
      <button class="kb-back" @click="goBack">← 返回</button>
      <div class="kb-title">
        <h2>知识库</h2>
        <span class="kb-sub">{{ character?.name ?? '未知角色' }}</span>
      </div>
      <button class="ghost" :disabled="busy === 'load'" @click="loadAll">刷新</button>
    </header>

    <div v-if="error" class="kb-error">{{ error }}</div>
    <div v-if="notice" class="kb-notice">{{ notice }}</div>

    <main class="kb-body">
      <section class="kb-card">
        <h3>文档</h3>
        <div class="kb-row">
          <input v-model="docTitle" placeholder="标题（可选）" />
          <select v-model="docScope" class="kb-select">
            <option value="world">world</option>
            <option value="self">self</option>
            <option value="relation">relation</option>
            <option value="rule">rule</option>
          </select>
          <select v-model="docVisibility" class="kb-select">
            <option value="public">public</option>
            <option value="private">private</option>
          </select>
        </div>
        <textarea v-model="docText" rows="4" placeholder="粘贴设定文本（Markdown 的 # 标题会作为分块前缀）" />
        <div class="kb-row">
          <button :disabled="busy === 'import' || !docText.trim()" @click="importText">导入文本</button>
          <button class="ghost" :disabled="busy === 'upload'" @click="fileInput?.click()">
            上传 .txt / .md
          </button>
          <input ref="fileInput" type="file" accept=".txt,.md" class="kb-file" @change="onFileChange" />
        </div>

        <div v-if="!documents.length" class="kb-muted">暂无文档</div>
        <div v-for="doc in documents" :key="doc.id" class="kb-item">
          <div class="kb-row spread">
            <strong>{{ doc.title }}</strong>
            <span class="kb-status" :class="`kb-status-${doc.status}`">{{ doc.status }}</span>
          </div>
          <div class="kb-muted">
            {{ doc.scope }} · {{ doc.visibility }} · 分块 {{ doc.chunk_count }} · 已索引
            {{ doc.indexed_count }}
            <template v-if="doc.source_uri"> · 来源 {{ doc.source_uri }}</template>
          </div>
          <div v-if="doc.error" class="kb-error">{{ doc.error }}</div>
          <div class="kb-row">
            <button class="ghost" @click="toggleChunks(doc)">
              {{ chunksMap[doc.id] ? '收起分块' : '查看分块' }}
            </button>
            <button class="ghost" @click="reindex(doc)">重建索引</button>
            <button class="ghost danger" @click="removeDoc(doc)">删除</button>
          </div>
          <div v-if="chunksMap[doc.id]" class="kb-chunks">
            <div v-for="chunk in chunksMap[doc.id]" :key="chunk.id" class="kb-chunk">
              <span class="kb-muted">
                #{{ chunk.seq + 1 }} · {{ chunk.tokens }} tok ·
                {{ chunk.indexed ? '已索引' : '未索引' }}
              </span>
              <pre>{{ chunk.content }}</pre>
            </div>
          </div>
        </div>
      </section>

      <section class="kb-card">
        <h3>Lore 设定</h3>
        <textarea v-model="loreContent" rows="3" placeholder="条目内容（如：影子讨厌被叫小白）" />
        <div class="kb-row">
          <input v-model="loreKeys" placeholder="触发关键词（逗号分隔）" />
          <input v-model.number="lorePriority" type="number" class="kb-num" title="优先级（越大越靠前）" />
        </div>
        <div class="kb-row">
          <label class="kb-check"><input v-model="loreConstant" type="checkbox" /> 常驻注入</label>
          <label class="kb-check"><input v-model="loreEnabled" type="checkbox" /> 启用</label>
          <label class="kb-check">
            扫描深度 <input v-model.number="loreScanDepth" type="number" class="kb-num" />
          </label>
        </div>
        <div class="kb-row">
          <button :disabled="busy === 'lore' || !loreContent.trim()" @click="saveLore">
            {{ editingLoreId !== null ? '保存修改' : '新建条目' }}
          </button>
          <button v-if="editingLoreId !== null" class="ghost" @click="resetLoreForm">取消</button>
        </div>

        <div v-if="!lores.length" class="kb-muted">暂无 lore 条目</div>
        <div v-for="lore in lores" :key="lore.id" class="kb-item">
          <div class="kb-row spread">
            <strong>
              <span v-if="lore.constant" class="kb-tag">常驻</span>
              <span v-if="!lore.enabled" class="kb-tag kb-tag-off">禁用</span>
              {{ lore.keys.join(' / ') || '（无关键词）' }}
            </strong>
            <span class="kb-muted">P{{ lore.priority }} · 深度 {{ lore.scan_depth }}</span>
          </div>
          <div class="kb-content">{{ lore.content }}</div>
          <div class="kb-row">
            <button class="ghost" @click="editLore(lore)">编辑</button>
            <button class="ghost danger" @click="removeLore(lore)">删除</button>
          </div>
        </div>
      </section>

      <section class="kb-card kb-card-wide">
        <h3>检索预览</h3>
        <div class="kb-row">
          <input
            v-model="searchQuery"
            placeholder="输入 query（可测试关键词命中与语义召回）"
            @keyup.enter="search"
          />
          <button :disabled="busy === 'search' || !searchQuery.trim()" @click="search">检索</button>
        </div>

        <template v-if="searchResult">
          <div class="kb-muted">
            组装区块 {{ searchResult.tokens }} tok · lore 命中 {{ searchResult.lore.length }} · 分块召回
            {{ searchResult.chunks.length }}
          </div>

          <div v-if="searchResult.lore.length" class="kb-sub-title">Lore 命中</div>
          <div v-for="hit in searchResult.lore" :key="hit.id" class="kb-item">
            <div class="kb-row spread">
              <strong>
                <span class="kb-tag">{{ hit.matched === 'constant' ? '常驻' : `命中 ${hit.matched}` }}</span>
                <span class="kb-tag" :class="{ 'kb-tag-off': !hit.included }">
                  {{ hit.included ? '已注入' : '未注入' }}
                </span>
              </strong>
              <span class="kb-muted">{{ hit.tokens }} tok</span>
            </div>
            <div class="kb-content">{{ hit.content }}</div>
          </div>

          <div v-if="searchResult.chunks.length" class="kb-sub-title">分块召回</div>
          <div v-for="hit in searchResult.chunks" :key="hit.id" class="kb-item">
            <div class="kb-row spread">
              <strong>
                <span class="kb-tag" :class="{ 'kb-tag-off': !hit.included }">
                  {{ hit.included ? '已注入' : '未注入' }}
                </span>
                {{ hit.title }} #{{ hit.seq + 1 }}
              </strong>
              <span class="kb-muted">score {{ hit.score }} · {{ hit.tokens }} tok</span>
            </div>
            <div class="kb-content">{{ hit.content }}</div>
          </div>

          <template v-if="searchResult.block">
            <div class="kb-sub-title">注入区块（预算内）</div>
            <pre class="kb-block">{{ searchResult.block }}</pre>
          </template>
        </template>
        <div v-else class="kb-muted">输入 query 后点击「检索」，查看双通道命中与最终注入区块</div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.kb-page {
  /* 本页配色：薄荷底色 + 深色按钮/边框（独立于全局紫色主题） */
  --kb-bg: #b9dec9;
  --kb-ink: #14301f;
  --kb-ink-soft: #2f5240;
  --kb-line: rgba(20, 48, 31, 0.38);
  --kb-card: rgba(255, 255, 255, 0.42);
  height: 100%;
  overflow-y: auto;
  padding: 0 24px 40px;
  background: var(--kb-bg);
  color: var(--kb-ink);
}

.kb-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 0 14px;
  border-bottom: 1px solid var(--kb-line);
  position: sticky;
  top: 0;
  background: var(--kb-bg);
  z-index: 5;
}

.kb-page .kb-back {
  background: transparent;
  border: 1px solid var(--kb-ink);
  color: var(--kb-ink);
  padding: 6px 14px;
  font-weight: 600;
}

.kb-page .kb-back:hover {
  background: rgba(20, 48, 31, 0.12);
}

.kb-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.kb-title h2 {
  margin: 0;
  color: var(--kb-ink);
  font-size: 18px;
  letter-spacing: 1px;
}

.kb-sub {
  color: var(--kb-ink-soft);
  font-size: 13px;
}

.kb-header .ghost {
  margin-left: auto;
}

.kb-body {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(440px, 1fr));
  gap: 16px;
  margin-top: 16px;
  max-width: 1240px;
}

.kb-card-wide {
  grid-column: 1 / -1;
}

.kb-card {
  background: var(--kb-card);
  border: 1px solid var(--kb-line);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kb-card h3 {
  margin: 0;
  color: var(--kb-ink);
  font-size: 15px;
}

.kb-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.kb-row.spread {
  justify-content: space-between;
}

.kb-page input:not([type='checkbox']),
.kb-page select,
.kb-page textarea {
  background: rgba(255, 255, 255, 0.6);
  color: var(--kb-ink);
  border: 1px solid var(--kb-line);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 13px;
  width: auto;
  flex: 1;
  min-width: 120px;
}

.kb-page textarea {
  width: 100%;
  flex: none;
  resize: vertical;
  font-family: inherit;
}

.kb-select {
  flex: none;
  width: 110px;
}

.kb-num {
  flex: none;
  width: 70px;
  min-width: 0;
}

.kb-page button {
  background: var(--kb-ink);
  color: var(--kb-bg);
  padding: 6px 14px;
  font-size: 13px;
}

.kb-page button.ghost {
  background: transparent;
  color: var(--kb-ink);
  border: 1px solid var(--kb-ink);
}

.kb-page button.danger {
  background: #7f1d1d;
  border-color: #7f1d1d;
  color: #fff;
}

.kb-page button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.kb-file {
  display: none;
}

.kb-item {
  border-top: 1px dashed var(--kb-line);
  padding-top: 8px;
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.kb-content {
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.kb-tag {
  display: inline-block;
  font-size: 11px;
  border: 1px solid var(--kb-line);
  border-radius: 999px;
  padding: 1px 8px;
  margin-right: 4px;
}

.kb-tag-off {
  opacity: 0.45;
}

.kb-status {
  font-size: 11px;
  border-radius: 999px;
  padding: 2px 8px;
  border: 1px solid var(--kb-line);
}

.kb-status-indexed {
  background: rgba(20, 48, 31, 0.16);
}

.kb-status-failed {
  background: rgba(127, 29, 29, 0.16);
}

.kb-chunks {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 280px;
  overflow-y: auto;
}

.kb-chunk pre,
.kb-block {
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid var(--kb-line);
  border-radius: 8px;
  padding: 8px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 4px 0 0;
}

.kb-block {
  max-height: 260px;
  overflow-y: auto;
}

.kb-sub-title {
  font-size: 13px;
  font-weight: 600;
  margin-top: 8px;
}

.kb-check {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--kb-ink-soft);
}

.kb-muted {
  color: var(--kb-ink-soft);
  font-size: 12px;
}

.kb-error {
  color: #7f1d1d;
  font-size: 13px;
  margin-top: 8px;
}

.kb-notice {
  color: #14532d;
  font-size: 13px;
  margin-top: 8px;
}
</style>
