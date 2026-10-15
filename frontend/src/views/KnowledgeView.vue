<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCharactersStore } from '../stores/characters'

const props = defineProps<{ id: string }>()
const router = useRouter()
const characters = useCharactersStore()

const character = computed(
  () => characters.list.find((c) => c.id === Number(props.id)) ?? null
)

onMounted(() => {
  if (!characters.list.length) characters.fetchList()
})

function goBack(): void {
  // 从角色卡进入则返回上一页；直接深链打开时回角色卡列表
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
      <span class="kb-badge">P2b 后端接入后启用</span>
    </header>

    <main class="kb-body">
      <section class="kb-card">
        <h3>文档</h3>
        <p class="kb-muted">导入 txt / md，自动分块并向量化；可查看分块、重建索引。</p>
        <div class="kb-placeholder">上传 / 粘贴区域（待接入）</div>
      </section>

      <section class="kb-card">
        <h3>Lore 设定</h3>
        <p class="kb-muted">World Info 风格条目：触发关键词、常驻注入、优先级。</p>
        <div class="kb-placeholder">条目编辑（待接入）</div>
      </section>

      <section class="kb-card">
        <h3>检索预览</h3>
        <p class="kb-muted">输入 query，查看关键词 / 向量命中片段与来源。</p>
        <div class="kb-placeholder">检索测试（待接入）</div>
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

.kb-badge {
  margin-left: auto;
  font-size: 12px;
  color: var(--kb-ink);
  border: 1px dashed var(--kb-line);
  border-radius: 999px;
  padding: 3px 10px;
}

.kb-body {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  margin-top: 20px;
  max-width: 1080px;
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

.kb-muted {
  margin: 0;
  color: var(--kb-ink-soft);
  font-size: 13px;
  line-height: 1.6;
}

.kb-placeholder {
  margin-top: 6px;
  border: 1px dashed var(--kb-line);
  border-radius: 8px;
  padding: 18px;
  text-align: center;
  color: var(--kb-ink-soft);
  font-size: 13px;
}

/* 本页按钮为深色系（覆盖全局紫色主题） */
.kb-page button {
  background: var(--kb-ink);
  color: var(--kb-bg);
}

.kb-page button.ghost {
  background: transparent;
  color: var(--kb-ink);
  border: 1px solid var(--kb-ink);
}
</style>
