import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import CharactersView from '../views/CharactersView.vue'
import CharacterEditView from '../views/CharacterEditView.vue'
import SettingsView from '../views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: ChatView },
    { path: '/characters', component: CharactersView },
    { path: '/characters/new', component: CharacterEditView },
    { path: '/characters/:id', component: CharacterEditView, props: true },
    { path: '/settings', component: SettingsView }
  ]
})

export default router