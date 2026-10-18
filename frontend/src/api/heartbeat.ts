import type { HeartbeatConfig, HeartbeatConfigUpdate, HeartbeatRun } from '../types/heartbeat'
import { get, post, put } from './client'

export function getHeartbeatConfig(characterId: number): Promise<HeartbeatConfig> {
  return get<HeartbeatConfig>(`/heartbeat/characters/${characterId}`)
}

export function updateHeartbeatConfig(
  characterId: number,
  payload: HeartbeatConfigUpdate
): Promise<HeartbeatConfig> {
  return put<HeartbeatConfig>(`/heartbeat/characters/${characterId}`, payload)
}

export function runHeartbeat(characterId: number, type = 'monologue'): Promise<HeartbeatRun> {
  return post<HeartbeatRun>(`/heartbeat/characters/${characterId}/run`, { type })
}

export function listHeartbeatRuns(characterId: number, limit = 20): Promise<HeartbeatRun[]> {
  return get<HeartbeatRun[]>(`/heartbeat/characters/${characterId}/runs?limit=${limit}`)
}
