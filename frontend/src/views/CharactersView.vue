<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCharactersStore } from '../stores/characters'

const characters = useCharactersStore()
const router = useRouter()

onMounted(() => characters.fetchList())

async function remove(id: number, name: string): Promise<void> {
  if (!confirm(`确认删除角色「${name}」？`)) return
  await characters.remove(id)
}
</script>

<template>
  <div class="page">
    <div class="row header">
      <h2>角色卡</h2>
      <button @click="router.push('/characters/new')">新建角色</button>
    </div>

    <div class="grid">
      <div v-for="c in characters.list" :key="c.id" class="panel card">
        <div class="row">
          <h3>{{ c.name }}</h3>
          <span class="muted">v{{ c.schema_version }}</span>
        </div>
        <p class="muted">{{ c.card.description || '（无描述）' }}</p>
        <div class="tags">
          <span v-for="t in c.card.tags" :key="t" class="tag">{{ t }}</span>
        </div>
        <div class="row actions">
          <button @click="router.push(`/characters/${c.id}`)">编辑</button>
          <button class="danger" @click="remove(c.id, c.name)">删除</button>
        </div>
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
  margin-bottom: 16px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tag {
  background: rgba(139, 92, 246, 0.2);
  color: var(--accent);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
}

.actions {
  margin-top: auto;
}
</style>