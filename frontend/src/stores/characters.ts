import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Character, CharacterCard, CharacterExt } from '../types/character'
import * as api from '../api/characters'

export const useCharactersStore = defineStore('characters', () => {
  const list = ref<Character[]>([])
  const loading = ref(false)

  async function fetchList(): Promise<void> {
    loading.value = true
    try {
      list.value = await api.listCharacters()
    } finally {
      loading.value = false
    }
  }

  async function get(id: number): Promise<Character> {
    return api.getCharacter(id)
  }

  async function create(card: CharacterCard, ext?: CharacterExt): Promise<Character> {
    const c = await api.createCharacter(card, ext)
    await fetchList()
    return c
  }

  async function update(id: number, card: CharacterCard, ext?: CharacterExt): Promise<Character> {
    const c = await api.updateCharacter(id, card, ext)
    await fetchList()
    return c
  }

  async function remove(id: number): Promise<void> {
    await api.deleteCharacter(id)
    await fetchList()
  }

  return { list, loading, fetchList, get, create, update, remove }
})