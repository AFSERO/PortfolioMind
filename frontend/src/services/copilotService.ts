import { api, ApiError, getAccessToken } from '@/services/api'
import type {
  ActionProposal,
  CancelProposalResponse,
  ConfirmProposalResponse,
  CopilotConversation,
  CopilotMessage,
  CopilotPageContext,
  CopilotV2ProgressEvent,
  SendMessageResponse,
} from '@/types/copilot'

interface ConversationItemResponse {
  status: string
  data: CopilotConversation
}

interface ConversationListResponse {
  status: string
  data: CopilotConversation[]
}

export const copilotService = {
  createConversation: (title?: string) =>
    api
      .post<ConversationItemResponse>('/copilot/conversations', { title })
      .then((res) => res.data),

  listConversations: () =>
    api
      .get<ConversationListResponse>('/copilot/conversations')
      .then((res) => res.data),

  getConversation: (conversationId: string) =>
    api
      .get<ConversationItemResponse>(`/copilot/conversations/${conversationId}`)
      .then((res) => res.data),

  deleteConversation: (conversationId: string) =>
    api.delete<void>(`/copilot/conversations/${conversationId}`),

  sendMessage: (
    conversationId: string,
    content: string,
    pageContext?: CopilotPageContext,
  ) =>
    api
      .post<SendMessageResponse>(`/copilot/conversations/${conversationId}/messages`, {
        content,
        page_context: pageContext,
      })
      .then((res) => res.data),

  sendV2Message: async (
    conversationId: string,
    content: string,
    onProgress?: (event: CopilotV2ProgressEvent) => void,
    signal?: AbortSignal,
  ): Promise<CopilotMessage> => {
    const token = getAccessToken()
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`/api/copilot/v2/conversations/${conversationId}/messages?stream=true`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ content }),
      credentials: 'include',
      signal,
    })

    if (!response.ok) {
      let errorMsg = 'Copilot V2 yanıt vermedi.'
      try {
        const errorJson = await response.json()
        errorMsg = errorJson.message || errorJson.detail || errorMsg
      } catch {
        errorMsg = response.statusText || errorMsg
      }
      throw new ApiError(errorMsg, response.status)
    }

    if (!response.body) {
      throw new ApiError('No response body stream received', 500)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let finalMessage: CopilotMessage | null = null

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const blocks = buffer.split('\n\n')
        buffer = blocks.pop() || ''

        for (const block of blocks) {
          const trimmed = block.trim()
          if (!trimmed || !trimmed.startsWith('data:')) continue

          const jsonStr = trimmed.replace(/^data:\s*/, '')
          try {
            const data = JSON.parse(jsonStr)

            if (data.type === 'FAILED') {
              throw new ApiError(data.message || 'Copilot V2 işlem hatası', 500)
            }

            if (data.type === 'FINAL') {
              finalMessage = data.message
            } else if (onProgress) {
              onProgress({
                type: data.type,
                message: data.message,
                tool: data.tool,
                target_profile: data.target_profile,
                profile: data.profile,
                effort: data.effort,
              })
            }
          } catch (err) {
            if (err instanceof ApiError) throw err
            console.error('Failed to parse SSE line from Copilot V2:', trimmed, err)
          }
        }
      }
    } finally {
      reader.releaseLock()
    }

    if (!finalMessage) {
      throw new ApiError('Copilot V2 stream tamamlandı ancak nihai yanıt alınamadı.', 500)
    }

    return finalMessage
  },

  getProposal: (proposalId: string) =>
    api
      .get<{ status: string; data: ActionProposal }>(`/copilot/v2/action-proposals/${proposalId}`)
      .then((res) => res.data)
      .catch(() =>
        api
          .get<{ status: string; data: ActionProposal }>(`/copilot/proposals/${proposalId}`)
          .then((res) => res.data)
      ),

  confirmProposal: async (proposalId: string, idempotencyKey?: string, confirmationText?: string) => {
    try {
      const res = await api.post<{ status: string; data: { proposal: ActionProposal; proposal_status?: string; execution_result?: any } }>(
        `/copilot/v2/action-proposals/${proposalId}/confirm`,
        { idempotency_key: idempotencyKey }
      )
      return {
        proposal: res.data.proposal,
        result: res.data.execution_result,
      }
    } catch (err: any) {
      if (err?.status === 404 || err?.response?.status === 404) {
        return api
          .post<ConfirmProposalResponse>(`/copilot/proposals/${proposalId}/confirm`, {
            idempotency_key: idempotencyKey,
            confirmation_text: confirmationText,
          })
          .then((res) => res.data)
      }
      throw err
    }
  },

  cancelProposal: async (proposalId: string, reason?: string) => {
    try {
      const res = await api.post<{ status: string; data: ActionProposal }>(
        `/copilot/v2/action-proposals/${proposalId}/cancel`,
        { reason }
      )
      return { proposal: res.data }
    } catch (err: any) {
      if (err?.status === 404 || err?.response?.status === 404) {
        return api
          .post<CancelProposalResponse>(`/copilot/proposals/${proposalId}/cancel`, { reason })
          .then((res) => res.data)
      }
      throw err
    }
  },

  uploadImportFile: (conversationId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api
      .postForm<SendMessageResponse>(`/copilot/conversations/${conversationId}/import/upload`, formData)
      .then((res) => res.data)
  },

  getImportBatch: (batchId: string) =>
    api
      .get<{ status: string; data: import('@/types/copilot').PortfolioImportBatch }>(
        `/copilot/import/batches/${batchId}`
      )
      .then((res) => res.data),

  resolveImportItem: (
    batchId: string,
    itemId: string,
    resolution: {
      quantity?: number
      average_cost?: number
      action_resolution?: import('@/types/copilot').ActionResolutionType
      selected_instrument_id?: string
    }
  ) =>
    api
      .post<{ status: string; data: import('@/types/copilot').PortfolioImportBatch }>(
        `/copilot/import/batches/${batchId}/items/${itemId}/resolve`,
        resolution
      )
      .then((res) => res.data),
}
