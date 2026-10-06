<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">ChatPhantasm</div>
      <nav>
        <RouterLink to="/">对话</RouterLink>
        <RouterLink to="/characters">角色卡</RouterLink>
        <RouterLink to="/settings">设置</RouterLink>
      </nav>
    </aside>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100%;
}

.sidebar {
  width: 180px;
  border-right: 1px solid var(--border);
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.brand {
  font-weight: 700;
  color: var(--accent);
  font-size: 16px;
}

nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

nav a {
  padding: 8px 12px;
  border-radius: 8px;
  color: var(--text);
}

nav a.router-link-exact-active {
  background: var(--accent);
  color: #fff;
}

.content {
  flex: 1;
  overflow: hidden;
}
</style>