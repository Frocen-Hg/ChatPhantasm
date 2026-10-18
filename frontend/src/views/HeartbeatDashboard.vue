<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useCharactersStore } from '../stores/characters'
import * as api from '../api/heartbeat'
import type { HeartbeatConfig, HeartbeatRun } from '../types/heartbeat'

const characters = useCharactersStore()
const characterId = ref<number | null>(null)
const config = ref<HeartbeatConfig | null>(null)
const runs = ref<HeartbeatRun[]>([])
const loading = ref(false)
const error = ref('')
const notice = ref('')

const form = reactive({
  enabled: false,
  interval_min: 60,
  types: ['monologue'] as string[],
  quietStart: '23:00',
  quietEnd: '08:00',
  daily_limit: 12,
  show_monologue: false
})
const saving = ref(false)

const runType = ref('monologue')
const running = ref(false)
const lastRun = ref<HeartbeatRun | null>(null)

const TYPE_OPTIONS = [
  { value: 'monologue', label: '内心独白', hint: '写私密内心记忆并影响心情/状态' },
  { value: 'proactive', label: '主动消息', hint: '用户久未说话且概率命中时主动开口' }
]
const TYPE_LABELS: Record<string, string> = { monologue: '内心独白', proactive: '主动消息' }
const STATUS_LABELS: Record<string, string> = { running: '进行中', done: '成功', failed: '失败' }
const BLOCKED_LABELS: Record<string, string> = {
  disabled: '未启用',
  quiet_hours: '静默时段内，结束后自动运行',
  daily_limit: '已达每日上限，明日恢复',
  no_type: '未选择产出类型'
}

// 表单与已保存配置的差异（避免"改了复选框但没保存"的误解）
const dirty = computed(() => {
  const cfg = config.value
  if (!cfg) return false
  return (
    form.enabled !== cfg.enabled ||
    form.interval_min !== cfg.interval_min ||
    form.daily_limit !== cfg.daily_limit ||
    form.show_monologue !== cfg.show_monologue ||
    form.quietStart !== (cfg.quiet_hours?.start ?? '') ||
    form.quietEnd !== (cfg.quiet_hours?.end ?? '') ||
    [...form.types].sort().join(',') !== [...cfg.types].sort().join(',')
  )
})

// 自动刷新：每 15s 拉取配置与运行记录（有未保存修改时不动表单）
const autoRefresh = ref(true)
let pollTimer: number | null = null

onMounted(async () => {
  await characters.fetchList()
  if (characters.list.length) {
    characterId.value = characters.list[0].id
    await load()
  }
  pollTimer = window.setInterval(() => {
    if (autoRefresh.value && characterId.value !== null && !saving.value && !running.value) {
      void refresh(false)
    }
  }, 15000)
})

onBeforeUnmount(() => {
  if (pollTimer !== null) window.clearInterval(pollTimer)
  pollTimer = null
})

function fillForm(cfg: HeartbeatConfig): void {
  form.enabled = cfg.enabled
  form.interval_min = cfg.interval_min
  form.types = [...cfg.types]
  form.quietStart = cfg.quiet_hours?.start ?? ''
  form.quietEnd = cfg.quiet_hours?.end ?? ''
  form.daily_limit = cfg.daily_limit
  form.show_monologue = cfg.show_monologue
}

async function refresh(fill: boolean): Promise<void> {
  if (characterId.value === null) return
  const keepForm = !fill && dirty.value
  try {
    const [cfg, list] = await Promise.all([
      api.getHeartbeatConfig(characterId.value),
      api.listHeartbeatRuns(characterId.value, 30)
    ])
    config.value = cfg
    runs.value = list
    if (!keepForm) fillForm(cfg)
  } catch (e: any) {
    if (fill) error.value = e?.message ?? String(e)
  }
}

async function load(): Promise<void> {
  if (characterId.value === null) return
  loading.value = true
  error.value = ''
  await refresh(true)
  loading.value = false
}

async function onCharacterChange(): Promise<void> {
  lastRun.value = null
  notice.value = ''
  await load()
}

function toggleType(value: string): void {
  const idx = form.types.indexOf(value)
  if (idx >= 0) form.types.splice(idx, 1)
  else form.types.push(value)
}

async function save(): Promise<void> {
  if (characterId.value === null) return
  if (!form.types.length) {
    error.value = '至少选择一种心跳类型'
    return
  }
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    const cfg = await api.updateHeartbeatConfig(characterId.value, {
      enabled: form.enabled,
      interval_min: form.interval_min,
      types: [...form.types],
      quiet_hours: { start: form.quietStart.trim(), end: form.quietEnd.trim() },
      daily_limit: form.daily_limit,
      show_monologue: form.show_monologue
    })
    config.value = cfg
    fillForm(cfg)
    notice.value = '配置已保存（同时同步到角色 ext.heartbeat）'
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    saving.value = false
  }
}

async function runOnce(): Promise<void> {
  if (characterId.value === null || running.value) return
  running.value = true
  error.value = ''
  notice.value = ''
  try {
    lastRun.value = await api.runHeartbeat(characterId.value, runType.value)
    if (lastRun.value.status === 'done') notice.value = '试跑完成'
    else error.value = `试跑失败：${lastRun.value.error}`
    await load()
  } catch (e: any) {
    error.value = e?.message ?? String(e)
  } finally {
    running.value = false
  }
}

function fmt(dt: string | null): string {
  return dt ? new Date(dt).toLocaleString() : '—'
}

function summarize(text: string, max = 80): string {
  if (!text) return '—'
  return text.length > max ? text.slice(0, max) + '…' : text
}

function statusClass(status: string): string {
  if (status === 'done') return 'ok'
  if (status === 'failed') return 'bad'
  return 'busy'
}
</script>

<template>
  <div class="page">
    <div class="row header">
      <h2>心跳面板</h2>
      <div class="row">
        <select v-model.number="characterId" @change="onCharacterChange">
          <option v-for="c in characters.list" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
        <label class="check">
          <input v-model="autoRefresh" type="checkbox" />
          自动刷新
        </label>
        <button class="ghost" :disabled="loading" @click="load">
          {{ loading ? '加载中…' : '刷新' }}
        </button>
      </div>
    </div>

    <div v-if="notice" class="notice">{{ notice }}</div>
    <div v-if="error" class="error">{{ error }}</div>

    <div v-if="config" class="panel config">
      <div class="row spread config-head">
        <strong>心跳配置</strong>
        <div class="row wrap status-row">
          <template v-if="!config.enabled">
            <span class="tag bad">未启用</span>
            <span class="muted">不会自动运行（仅试跑）；勾选「启用心跳」并保存后开始调度</span>
          </template>
          <template v-else>
            <span class="tag ok">已启用</span>
            <span class="muted">
              今日 {{ config.today_count }}/{{ config.daily_limit }} 次<template
                v-if="config.today_manual"
              >
                （含试跑 {{ config.today_manual }}）</template
              >
            </span>
            <span v-if="config.blocked_reason" class="tag busy">
              {{ BLOCKED_LABELS[config.blocked_reason] ?? config.blocked_reason }}
            </span>
            <span v-else-if="config.due" class="tag ok">已到期，等待调度（≤30s 自动触发）</span>
            <span v-else class="muted">下次 {{ fmt(config.next_run_at) }}</span>
          </template>
        </div>
      </div>

      <label class="check">
        <input v-model="form.enabled" type="checkbox" />
        启用心跳（角色不依赖用户输入进行内心活动）
      </label>

      <div class="row wrap">
        <div class="field grow">
          <label>间隔（分钟）</label>
          <input v-model.number="form.interval_min" type="number" min="1" max="10080" />
        </div>
        <div class="field grow">
          <label>每日上限（0 表示不运行）</label>
          <input v-model.number="form.daily_limit" type="number" min="0" max="1000" />
        </div>
        <div class="field grow">
          <label>静默开始（HH:MM，空为不静默）</label>
          <input v-model="form.quietStart" placeholder="23:00" />
        </div>
        <div class="field grow">
          <label>静默结束</label>
          <input v-model="form.quietEnd" placeholder="08:00" />
        </div>
      </div>

      <div class="field">
        <label>产出类型</label>
        <div class="row wrap">
          <label v-for="t in TYPE_OPTIONS" :key="t.value" class="check">
            <input
              type="checkbox"
              :checked="form.types.includes(t.value)"
              @change="toggleType(t.value)"
            />
            {{ t.label }}<span class="muted">（{{ t.hint }}）</span>
          </label>
        </div>
      </div>

      <label class="check">
        <input v-model="form.show_monologue" type="checkbox" />
        聊天页展示内心独白（仅前端展示，不影响注入）
      </label>

      <div class="row">
        <button :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button>
        <span v-if="dirty" class="dirty-hint">有未保存的修改，保存后生效</span>
        <span v-else class="muted">配置已保存{{ config.enabled ? '，按间隔自动运行' : '' }}</span>
      </div>
    </div>

    <div class="panel tester">
      <div class="row spread">
        <strong>试跑</strong>
        <span class="muted">手动触发一次（绕过开关/静默/上限，不改动排程；计入今日次数）</span>
      </div>
      <div class="row wrap">
        <div class="field" style="width: 160px">
          <label>类型</label>
          <select v-model="runType">
            <option v-for="t in TYPE_OPTIONS" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </div>
        <button :disabled="running || characterId === null" @click="runOnce">
          {{ running ? '生成中…' : '试跑一次' }}
        </button>
      </div>
      <div v-if="lastRun" class="last-run">
        <div class="row">
          <span class="tag">{{ TYPE_LABELS[lastRun.type] ?? lastRun.type }}</span>
          <span v-if="lastRun.is_manual" class="tag tag-manual">试跑</span>
          <span class="tag" :class="statusClass(lastRun.status)">
            {{ STATUS_LABELS[lastRun.status] ?? lastRun.status }}
          </span>
          <span class="muted">{{ lastRun.tokens }} tok · {{ fmt(lastRun.finished_at) }}</span>
        </div>
        <p v-if="lastRun.output" class="content">{{ lastRun.output }}</p>
        <p v-if="lastRun.error" class="error">{{ lastRun.error }}</p>
      </div>
    </div>

    <div class="panel records">
      <div class="row spread">
        <strong>运行记录</strong>
        <span class="muted">最近 {{ runs.length }} 条</span>
      </div>
      <div v-if="!runs.length" class="muted">暂无记录（开启心跳或点击试跑）</div>
      <div v-for="r in runs" :key="r.id" class="record">
        <div class="row spread">
          <div class="row">
            <span class="tag">{{ TYPE_LABELS[r.type] ?? r.type }}</span>
            <span v-if="r.is_manual" class="tag tag-manual">试跑</span>
            <span class="tag" :class="statusClass(r.status)">
              {{ STATUS_LABELS[r.status] ?? r.status }}
            </span>
            <span class="muted">#{{ r.id }} · {{ r.tokens }} tok</span>
          </div>
          <span class="muted">{{ fmt(r.started_at) }}</span>
        </div>
        <p v-if="r.output" class="content">{{ summarize(r.output) }}</p>
        <p v-if="r.error" class="error">{{ r.error }}</p>
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
  width: 180px;
}

.config,
.tester,
.records {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 760px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field.grow {
  flex: 1;
  min-width: 150px;
}

.wrap {
  flex-wrap: wrap;
  align-items: flex-end;
}

.check {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 13px;
}

label {
  font-size: 13px;
  color: var(--muted);
}

.spread {
  justify-content: space-between;
}

.tag {
  background: rgba(139, 92, 246, 0.2);
  color: var(--accent);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  margin-right: 6px;
}

.tag.ok {
  background: rgba(74, 222, 128, 0.15);
  color: #4ade80;
}

.tag.bad {
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
}

.tag.busy {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.tag.tag-manual {
  background: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
}

.config-head {
  align-items: flex-start;
}

.status-row {
  justify-content: flex-end;
  flex: 1;
}

.dirty-hint {
  color: #f59e0b;
  font-size: 13px;
}

.record,
.last-run {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.content {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.5;
  font-size: 13px;
}

.notice {
  color: #4ade80;
  font-size: 13px;
}

.error {
  color: #f87171;
  font-size: 13px;
}
</style>
