import type { Character, CharacterCard, CharacterExt } from '../types/character'
import { del, get, post, put } from './client'

export function listCharacters(): Promise<Character[]> {
  return get<Character[]>('/characters')
}

export function getCharacter(id: number): Promise<Character> {
  return get<Character>(`/characters/${id}`)
}

export function createCharacter(card: CharacterCard, ext?: CharacterExt): Promise<Character> {
  return post<Character>('/characters', { card, ext })
}

export function updateCharacter(id: number, card: CharacterCard, ext?: CharacterExt): Promise<Character> {
  return put<Character>(`/characters/${id}`, { card, ext })
}

export function deleteCharacter(id: number): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/characters/${id}`)
}