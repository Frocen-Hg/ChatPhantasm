export interface ChatRequest {
  character_id: number
  conversation_id?: number | null
  content: string
}