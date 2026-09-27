import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ProviderConfig } from '../types/provider'
import * as api from '../api/providers'

export const useProvidersStore = defineStore('providers', () => {
  const list = ref<ProviderConfig[]>([])

  async function fetchList(): Promise<void> {
    list.value = await api.listProviders()
  }

  async function create(payload: api.ProviderPayload): Promise<ProviderConfig> {
    const p = await api.createProvider(payload)
    await fetchList()
    return p
  }

  async function remove(id: number): Promise<void> {
    await api.deleteProvider(id)
    await fetchList()
  }

  return { list, fetchList, create, remove }
})