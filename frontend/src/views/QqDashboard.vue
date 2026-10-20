<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useCharactersStore } from '../stores/characters'
import * as api from '../api/qq'
import type {
  QqBinding,
  QqBindingPayload,
  QqGroup,
  QqMember,
  QqReply,
  QqReplyMode,
  QqStatus
} from '../types/qq'

interface MemberDraft {
  tags: string
  note: string
  ignored: boolean
  saving: boolean
}

const characters = useCharactersStore()
const status = ref<QqStatus | null>(null)
const bindings = ref<QqBinding[]>([])
const members = ref<QqMember[]>([])
const replies = ref<QqReply[]>([])
const groups = ref<QqGroup[]>([])
const selectedId = ref<number | null>(null)
const loading = ref(false)
const saving = ref(false)
const notice = ref('')
const error = ref('')
const search = ref('')
const groupFilter = ref('')
const testText = ref('')
const memberDrafts = reactive<Record<number, MemberDraft>>({})

const form = reactive({
  character_id: 0,
  group_id: '',
  bot_uin: '',
  group_name: '',
  enabled: true,
  reply_mode: 'mention' as QqReplyMode,
  keywordsText: '',
  reply_probability: 0.15,
  min_interval_sec: 90,
  max_replies_per_hour: 12,
  max_replies_per_day: 80,
  debounce_sec: 3,
  mention_bypass_cooldown: true,
  proactive_enabled: false,
  group_note: ''
})

const selected = computed(() => bindings.value.find((b) => b.id === selectedId.value) ?? null)
const filteredGroups = computed(() => {
  const q = groupFilter.value.trim().toLowerCase()
  if (!q) return groups.value
  return groups.value.filter(
    (g) => g.group_name.toLowerCase().includes(q) || g.group_id.includes(q)
  )
})

const MODE_OPTIONS: { value: QqReplyMode; label: string; hint: string }[] = [
  { value: 'mention', label: '仅被 @ / 回复', hint: '最克制：只有明确叫到角色时发言' },
  { value: 'keyword', label: '@ 或关键词', hint: '命中关键词时接话，适合固定话题' },
  { value: 'ambient', label: '@ / 关键词 + 概率闲聊', hint: '其他消息按概率自然插话' },
  { value: 'all', label: '每条都回', hint: '高风险：只建议在测试群使用' }
]
const MODE_LABELS: Record<string, string> = {
  mention: '仅 @',
  keyword: '关键词',
  ambient: '概率闲聊',
  all: '每条都回'
}
const TRIGGER_LABELS: Record<string, string> = {
  mention: '@ 触发',
  keyword: '关键词',
  ambient: '概率插话',
  all: '全量',
  proactive: '心跳主动'
}
const ROLE_LABELS: Record<string, string> = { owner: '群主', admin: '管理员', member: '成员' }

let pollTimer: number | null = null

onMounted(async () => {
  await characters.fetchList()
  await refreshStatus()
  await loadBindings()
  pollTimer = window.setInterval(() => {
    void refreshStatus(true)
  }, 10000)
})

onBeforeUnmount(() => {
  if (pollTimer !== null) window.clearInterval(pollTimer)
  pollTimer = null
})

async function refreshStatus(silent = false): Promise<void> {
  try {
    status.value = await api.getQqStatus()
    const bots = status.value.bots.map((b) => b.self_id)
    for (const binding of bindings.value) {
      binding.connected = binding.bot_uin
        ? status.value.connected && bots.includes(binding.bot_uin)
        : status.value.connected
    }
  } catch (e: any) {
    if (!silent) error.value = e?.message ?? String(e)
  }
}

async function loadBindings(): Promise<void> {
  loading.value = true
  try {
    bindings.value = await api.listQqBindings()
    if (selectedId.value !== null && bindings.value.some((b) => b.id === selectedId.value)) {
      const current = bindings.value.find((b) => b.id === selectedId.value)!
      fillForm(current)
      await loadMembers()
      await loadReplies()
    } else if (bindings.value.length) {
      await selectBinding(bindings.value[0].id)
    } else {
      newBinding()
    }
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    loading.value = false
  }
}

async function refreshAll(): Promise<void> {
  notice.value = ''
  error.value = ''
  await refreshStatus()
  if (selectedId.value !== null && dirty.value) {
    await Promise.all([loadMembers(), loadReplies()])
    return
  }
  await loadBindings()
}

const dirty = computed(() => {
  const b = selected.value
  if (!b) return false
  return (
    b.character_id !== Number(form.character_id) ||
    b.group_id !== form.group_id ||
    b.bot_uin !== form.bot_uin ||
    b.group_name !== form.group_name ||
    b.enabled !== form.enabled ||
    b.reply_mode !== form.reply_mode ||
    b.keywords.join('\n') !== form.keywordsText ||
    Number(b.reply_probability) !== Number(form.reply_probability) ||
    b.min_interval_sec !== Number(form.min_interval_sec) ||
    b.max_replies_per_hour !== Number(form.max_replies_per_hour) ||
    b.max_replies_per_day !== Number(form.max_replies_per_day) ||
    Number(b.debounce_sec) !== Number(form.debounce_sec) ||
    b.mention_bypass_cooldown !== form.mention_bypass_cooldown ||
    b.proactive_enabled !== form.proactive_enabled ||
    b.group_note !== form.group_note
  )
})

function fillForm(binding: QqBinding): void {
  form.character_id = binding.character_id
  form.group_id = binding.group_id
  form.bot_uin = binding.bot_uin
  form.group_name = binding.group_name
  form.enabled = binding.enabled
  form.reply_mode = binding.reply_mode
  form.keywordsText = binding.keywords.join('\n')
  form.reply_probability = binding.reply_probability
  form.min_interval_sec = binding.min_interval_sec
  form.max_replies_per_hour = binding.max_replies_per_hour
  form.max_replies_per_day = binding.max_replies_per_day
  form.debounce_sec = binding.debounce_sec
  form.mention_bypass_cooldown = binding.mention_bypass_cooldown
  form.proactive_enabled = binding.proactive_enabled
  form.group_note = binding.group_note
}

function newBinding(): void {
  selectedId.value = null
  members.value = []
  replies.value = []
  for (const key of Object.keys(memberDrafts)) delete memberDrafts[Number(key)]
  form.character_id = characters.list[0]?.id ?? 0
  form.group_id = ''
  form.bot_uin = ''
  form.group_name = ''
  form.enabled = true
  form.reply_mode = 'mention'
  form.keywordsText = ''
  form.reply_probability = 0.15
  form.min_interval_sec = 90
  form.max_replies_per_hour = 12
  form.max_replies_per_day = 80
  form.debounce_sec = 3
  form.mention_bypass_cooldown = true
  form.proactive_enabled = false
  form.group_note = ''
  notice.value = ''
  error.value = ''
}

async function selectBinding(id: number): Promise<void> {
  selectedId.value = id
  const binding = bindings.value.find((b) => b.id === id)
  if (binding) fillForm(binding)
  notice.value = ''
  error.value = ''
  await Promise.all([loadMembers(), loadReplies()])
}

async function loadMembers(): Promise<void> {
  if (selectedId.value === null) return
  try {
    members.value = await api.listQqMembers(selectedId.value, search.value.trim())
    for (const m of members.value) {
      memberDrafts[m.id] = {
        tags: m.tags.join('，'),
        note: m.note,
        ignored: m.ignored,
        saving: false
      }
    }
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  }
}

async function loadReplies(): Promise<void> {
  if (selectedId.value === null) return
  try {
    replies.value = await api.listQqReplies(selectedId.value, 30)
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  }
}

function splitKeywords(text: string): string[] {
  return text
    .split(/[\n,，]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function splitTags(text: string): string[] {
  return text
    .split(/[,，、]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function buildPayload(): QqBindingPayload | null {
  if (!form.character_id) {
    error.value = '请先选择角色'
    return null
  }
  if (!form.group_id.trim()) {
    error.value = '群号不能为空'
    return null
  }
  return {
    character_id: Number(form.character_id),
    group_id: form.group_id.trim(),
    bot_uin: form.bot_uin.trim(),
    group_name: form.group_name.trim(),
    enabled: form.enabled,
    reply_mode: form.reply_mode,
    keywords: splitKeywords(form.keywordsText),
    reply_probability: Number(form.reply_probability),
    min_interval_sec: Number(form.min_interval_sec),
    max_replies_per_hour: Number(form.max_replies_per_hour),
    max_replies_per_day: Number(form.max_replies_per_day),
    debounce_sec: Number(form.debounce_sec),
    mention_bypass_cooldown: form.mention_bypass_cooldown,
    proactive_enabled: form.proactive_enabled,
    group_note: form.group_note
  }
}

async function save(): Promise<void> {
  const payload = buildPayload()
  if (payload === null) return
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    let saved: QqBinding
    const created = selectedId.value === null
    if (created) {
      saved = await api.createQqBinding(payload)
    } else {
      saved = await api.updateQqBinding(selectedId.value as number, payload)
    }
    await refreshStatus()
    await loadBindings()
    await selectBinding(saved.id)
    notice.value = created ? '绑定已创建，等待群消息' : '绑定配置已保存'
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    saving.value = false
  }
}

async function removeBinding(): Promise<void> {
  if (selectedId.value === null) return
  if (!confirm('确认删除此 QQ 绑定？群成员标签与发言日志会一并删除，聊天记录保留。')) return
  try {
    await api.deleteQqBinding(selectedId.value)
    selectedId.value = null
    for (const key of Object.keys(memberDrafts)) delete memberDrafts[Number(key)]
    await refreshStatus()
    await loadBindings()
    notice.value = '绑定已删除'
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  }
}

async function loadGroups(): Promise<void> {
  error.value = ''
  try {
    groups.value = await api.listQqGroups(form.bot_uin.trim())
    if (!groups.value.length) notice.value = '已连接，但账号没有群列表'
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  }
}

function pickGroup(group: QqGroup): void {
  form.group_id = group.group_id
  form.group_name = group.group_name
  groupFilter.value = ''
  groups.value = []
  notice.value = `已选择群「${group.group_name || group.group_id}」`
}

async function saveMember(member: QqMember): Promise<void> {
  const draft = memberDrafts[member.id]
  if (!draft) return
  draft.saving = true
  error.value = ''
  try {
    const updated = await api.updateQqMember(member.id, {
      tags: splitTags(draft.tags),
      note: draft.note.trim(),
      ignored: draft.ignored
    })
    const idx = members.value.findIndex((m) => m.id === member.id)
    if (idx >= 0) members.value[idx] = updated
    memberDrafts[member.id] = {
      tags: updated.tags.join('，'),
      note: updated.note,
      ignored: updated.ignored,
      saving: false
    }
    notice.value = `已更新 ${updated.display_name} 的标签`
  } catch (e: any) {
    error.value = e?.message ?? String(e)
    draft.saving = false
  }
}

async function sendTest(): Promise<void> {
  if (selectedId.value === null || !testText.value.trim()) return
  error.value = ''
  notice.value = ''
  try {
    await api.sendQqTest(selectedId.value, { text: testText.value.trim() })
    notice.value = '测试消息已发送'
    testText.value = ''
    await loadReplies()
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  }
}

function fmt(dt: string | null): string {
  return dt ? new Date(dt).toLocaleString() : '—'
}

function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role
}

function statusClass(binding: QqBinding): string {
  if (!binding.enabled) return 'bad'
  return binding.connected ? 'ok' : 'busy'
}

function statusText(binding: QqBinding): string {
  if (!binding.enabled) return '停用'
  return binding.connected ? '在线' : '离线'
}
</script>

<template>
  <div class="page">
    <div class="row header">
      <h2>QQ 群聊</h2>
      <div class="row">
        <span class="tag" :class="status?.connected ? 'ok' : 'bad'">
          {{ status?.connected ? 'NapCat 已连接' : 'NapCat 未连接' }}
        </span>
        <button class="ghost" :disabled="loading" @click="refreshAll">
          {{ loading ? '加载中…' : '刷新' }}
        </button>
        <button @click="newBinding">新增绑定</button>
      </div>
    </div>

    <div v-if="notice" class="notice">{{ notice }}</div>
    <div v-if="error" class="error">{{ error }}</div>

    <div class="panel connection">
      <div class="row spread">
        <strong>NapCat 连接</strong>
        <span class="muted">
          反向 WebSocket → <code>ws://127.0.0.1:8000/api/v1/qq/ws</code>
        </span>
      </div>
      <div v-if="status?.bots.length" class="bot-list">
        <span v-for="bot in status.bots" :key="bot.self_id" class="tag ok">
          QQ {{ bot.self_id }} · 连接于 {{ fmt(bot.connected_at) }}
        </span>
      </div>
      <p v-else class="muted">
        尚未收到 NapCat 连接。请在 NapCat WebUI「网络配置」中启用反向 WebSocket，
        地址填上方 URL；token 与本项目 .env 的 <code>QQ_TOKEN</code> 保持一致（留空则不校验）。
      </p>
      <div class="muted">
        已绑定 {{ status?.bindings ?? 0 }} 个群，其中启用 {{ status?.enabled_bindings ?? 0 }} 个。
      </div>
    </div>

    <div class="layout">
      <aside class="panel list">
        <div class="row spread">
          <strong>群绑定</strong>
          <span class="muted">{{ bindings.length }}</span>
        </div>
        <button
          v-for="b in bindings"
          :key="b.id"
          class="binding"
          :class="{ active: b.id === selectedId }"
          @click="selectBinding(b.id)"
        >
          <div class="row spread">
            <strong>{{ b.group_name || b.group_id }}</strong>
            <span class="tag" :class="statusClass(b)">{{ statusText(b) }}</span>
          </div>
          <div class="muted">{{ b.group_id }} · {{ b.character_name }}</div>
          <div class="muted">
            今日 {{ b.day_replies }}/{{ b.max_replies_per_day || '∞' }} · 1h
            {{ b.hour_replies }}/{{ b.max_replies_per_hour || '∞' }} · 成员 {{ b.member_count }}
          </div>
        </button>
        <p v-if="!bindings.length" class="muted">还没有绑定群。点击右上角「新增绑定」开始。</p>
      </aside>

      <section class="panel editor">
        <div class="row spread">
          <h3>{{ selectedId === null ? '新增绑定' : '编辑绑定' }}</h3>
          <span v-if="selected" class="muted">最后活跃 {{ fmt(selected.last_active_at) }}</span>
        </div>

        <label class="check">
          <input v-model="form.enabled" type="checkbox" />
          启用此群（关闭后不读取消息、不回复）
        </label>

        <div class="form-grid">
          <label class="field">
            <span>角色</span>
            <select v-model.number="form.character_id">
              <option v-for="c in characters.list" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </label>

          <label class="field">
            <span>机器人 QQ（留空=任意已连接账号）</span>
            <input v-model="form.bot_uin" placeholder="例如 123456789" />
          </label>

          <label class="field">
            <span>群号</span>
            <div class="row">
              <input v-model="form.group_id" placeholder="QQ 群号" />
              <button class="ghost" type="button" @click="loadGroups">群列表</button>
            </div>
          </label>

          <label class="field">
            <span>群名称（备注用）</span>
            <input v-model="form.group_name" placeholder="例如 技术交流群" />
          </label>
        </div>

        <div v-if="groups.length" class="group-picker">
          <div class="row spread">
            <strong>选择群</strong>
            <button class="ghost" type="button" @click="groups = []">关闭</button>
          </div>
          <input v-model="groupFilter" placeholder="搜索群名/群号" />
          <div class="group-list">
            <button
              v-for="g in filteredGroups"
              :key="g.group_id"
              class="group-chip"
              type="button"
              @click="pickGroup(g)"
            >
              {{ g.group_name || g.group_id }}
              <span class="muted">{{ g.group_id }}</span>
            </button>
          </div>
        </div>

        <div class="form-grid">
          <label class="field">
            <span>触发方式</span>
            <select v-model="form.reply_mode">
              <option v-for="m in MODE_OPTIONS" :key="m.value" :value="m.value">
                {{ m.label }}
              </option>
            </select>
            <span class="hint">
              {{ MODE_OPTIONS.find((m) => m.value === form.reply_mode)?.hint }}
            </span>
          </label>

          <label class="field">
            <span>闲聊概率（0-1）</span>
            <input v-model.number="form.reply_probability" type="number" min="0" max="1" step="0.05" />
            <span class="hint">仅「概率闲聊」模式生效；被 @ 或命中关键词不受影响</span>
          </label>

          <label class="field">
            <span>回复最小间隔（秒）</span>
            <input v-model.number="form.min_interval_sec" type="number" min="0" step="10" />
          </label>

          <label class="field">
            <span>合并消息窗口（秒）</span>
            <input v-model.number="form.debounce_sec" type="number" min="0.5" max="30" step="0.5" />
            <span class="hint">连续多条消息合并成一轮，避免逐条刷屏</span>
          </label>

          <label class="field">
            <span>每小时上限（0=不限）</span>
            <input v-model.number="form.max_replies_per_hour" type="number" min="0" />
          </label>

          <label class="field">
            <span>每日上限（0=不限）</span>
            <input v-model.number="form.max_replies_per_day" type="number" min="0" />
          </label>
        </div>

        <label class="field">
          <span>关键词（换行或逗号分隔）</span>
          <textarea
            v-model="form.keywordsText"
            rows="3"
            placeholder="角色名&#10;在吗&#10;怎么看"
          ></textarea>
        </label>

        <label class="field">
          <span>本群说明（可选）</span>
          <textarea
            v-model="form.group_note"
            rows="3"
            placeholder="例如：这是一个游戏群，大家说话比较随意；角色在这里是潜水的老群友。"
          ></textarea>
        </label>

        <div class="row wrap checks">
          <label class="check">
            <input v-model="form.mention_bypass_cooldown" type="checkbox" />
            被 @ 时跳过最小间隔
          </label>
          <label class="check">
            <input v-model="form.proactive_enabled" type="checkbox" />
            允许心跳主动消息发到此群
          </label>
        </div>
        <p class="muted">
          心跳每轮只会投递到该角色最近活跃、且勾选了此选项的群；多群场景下不会同时刷屏。
        </p>

        <div class="row wrap actions">
          <button :disabled="saving" @click="save">
            {{ saving ? '保存中…' : selectedId === null ? '创建绑定' : '保存配置' }}
          </button>
          <button v-if="selectedId !== null" class="danger" @click="removeBinding">删除绑定</button>
          <div v-if="selectedId !== null" class="test-send">
            <input v-model="testText" placeholder="发送一条测试消息…" @keyup.enter="sendTest" />
            <button class="ghost" :disabled="!testText.trim()" @click="sendTest">发送测试</button>
          </div>
        </div>
      </section>
    </div>

    <div v-if="selectedId !== null" class="lower">
      <div class="panel">
        <div class="row spread">
          <div>
            <h3>群成员标签</h3>
            <p class="muted">
              标签与印象会作为背景注入群聊上下文；勾选「忽略」后不回应此人，也不写入角色上下文。
              成员会在首次发言后自动出现。
            </p>
          </div>
          <div class="row">
            <input v-model="search" placeholder="搜索昵称/QQ/备注" @keyup.enter="loadMembers" />
            <button class="ghost" @click="loadMembers">搜索</button>
          </div>
        </div>
        <div class="table-wrap">
          <table v-if="members.length">
            <thead>
              <tr>
                <th>成员</th>
                <th>标签</th>
                <th>印象 / 关系备注</th>
                <th>忽略</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in members" :key="m.id" v-show="memberDrafts[m.id]">
                <td>
                  <div>{{ m.display_name }}</div>
                  <div class="muted">
                    QQ {{ m.user_id }} · {{ roleLabel(m.role) }} · {{ m.message_count }} 条 ·
                    {{ fmt(m.last_message_at) }}
                  </div>
                </td>
                <td>
                  <input v-model="memberDrafts[m.id].tags" placeholder="朋友，同事，管理员" />
                </td>
                <td>
                  <input v-model="memberDrafts[m.id].note" placeholder="角色对他的印象/关系" />
                </td>
                <td>
                  <input v-model="memberDrafts[m.id].ignored" type="checkbox" />
                </td>
                <td>
                  <button
                    class="ghost"
                    :disabled="memberDrafts[m.id].saving"
                    @click="saveMember(m)"
                  >
                    {{ memberDrafts[m.id].saving ? '…' : '保存' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="muted">暂无成员记录。</p>
        </div>
      </div>

      <div class="panel">
        <h3>最近回复</h3>
        <div v-if="replies.length" class="reply-list">
          <div v-for="r in replies" :key="r.id" class="reply">
            <div class="row spread">
              <span class="tag">{{ TRIGGER_LABELS[r.trigger] ?? r.trigger }}</span>
              <span class="muted">{{ fmt(r.created_at) }}</span>
            </div>
            <div class="reply-content">{{ r.content }}</div>
          </div>
        </div>
        <p v-else class="muted">还没有回复记录。</p>
      </div>
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
  margin-bottom: 12px;
}

.spread {
  justify-content: space-between;
}

.wrap {
  flex-wrap: wrap;
}

.notice,
.error {
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
  font-size: 13px;
}

.notice {
  background: rgba(34, 197, 94, 0.15);
  color: #86efac;
}

.error {
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
}

.connection {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.bot-list {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

code {
  background: rgba(139, 92, 246, 0.15);
  padding: 1px 5px;
  border-radius: 4px;
}

.layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.binding {
  text-align: left;
  background: #1a1a1a;
  border: 1px solid var(--border);
  color: var(--text);
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
}

.binding.active {
  border-color: var(--accent);
  background: rgba(139, 92, 246, 0.15);
}

.tag {
  background: rgba(139, 92, 246, 0.2);
  color: var(--accent);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  white-space: nowrap;
}

.tag.ok {
  background: rgba(34, 197, 94, 0.18);
  color: #86efac;
}

.tag.bad {
  background: rgba(239, 68, 68, 0.18);
  color: #fca5a5;
}

.tag.busy {
  background: rgba(245, 158, 11, 0.18);
  color: #fcd34d;
}

.editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.field > span {
  color: var(--muted);
}

.hint {
  color: var(--muted);
  font-size: 11px;
}

.check {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
}

.checks {
  gap: 16px;
}

.group-picker {
  border: 1px dashed var(--border);
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 160px;
  overflow-y: auto;
}

.group-chip {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 6px 10px;
  font-size: 13px;
}

.actions {
  gap: 8px;
}

.test-send {
  display: flex;
  gap: 6px;
  flex: 1;
  min-width: 260px;
}

.lower {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr);
  gap: 12px;
  margin-top: 12px;
}

.table-wrap {
  overflow-x: auto;
  margin-top: 8px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid rgba(139, 92, 246, 0.18);
  vertical-align: middle;
}

th {
  color: var(--muted);
  font-weight: 500;
}

.reply-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
  max-height: 420px;
  overflow-y: auto;
}

.reply {
  border-bottom: 1px solid rgba(139, 92, 246, 0.18);
  padding-bottom: 8px;
}

.reply-content {
  margin-top: 4px;
  white-space: pre-wrap;
  font-size: 13px;
}

@media (max-width: 1100px) {
  .layout,
  .lower {
    grid-template-columns: 1fr;
  }
}
</style>
