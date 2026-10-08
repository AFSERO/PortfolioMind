import { useEffect, useRef, useState } from 'react'
import {
  Bot,
  Database,
  Loader2,
  MessageSquare,
  Paperclip,
  Plus,
  Send,
  Sparkles,
  User as UserIcon,
} from 'lucide-react'
import { toast } from 'sonner'

import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import { PortfolioImportCard } from '@/components/copilot/PortfolioImportCard'
import { ActionProposalCard } from '@/components/copilot/ActionProposalCard'
import { SimulationCard } from '@/components/copilot/SimulationCard'
import { ExternalSourcesSection } from '@/components/copilot/ExternalSourcesSection'

import { V2DiagnosticsSection } from '@/components/copilot/V2DiagnosticsSection'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { copilotService } from '@/services/copilotService'
import type {
  ActionResolutionType,
  ContextProvenanceItem,
  CopilotConversation,
  CopilotMessage,
  CopilotV2ProgressEvent,
} from '@/types/copilot'
import { cn } from '@/utils/cn'

export default function CopilotPage() {
  const [conversations, setConversations] = useState<CopilotConversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<CopilotMessage[]>([])
  const [inputContent, setInputContent] = useState('')
  const [loadingConversations, setLoadingConversations] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [sending, setSending] = useState(false)
  const [copilotVersion, setCopilotVersion] = useState<'v1' | 'v2'>(() => {
    if (typeof window !== 'undefined') {
      return (localStorage.getItem('portfoliomind_copilot_version') as 'v1' | 'v2') || 'v1'
    }
    return 'v1'
  })
  const [v2Progress, setV2Progress] = useState<CopilotV2ProgressEvent | null>(null)

  const handleVersionChange = (ver: 'v1' | 'v2') => {
    setCopilotVersion(ver)
    if (typeof window !== 'undefined') {
      localStorage.setItem('portfoliomind_copilot_version', ver)
    }
    toast.info(`Copilot ${ver === 'v2' ? 'V2 Beta (Codex Engine)' : 'V1'} seçildi.`)
  }

  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }

  // Load conversations on mount
  useEffect(() => {
    async function fetchConversations() {
      try {
        setLoadingConversations(true)
        const list = await copilotService.listConversations()
        setConversations(list)
        if (list.length > 0) {
          setActiveConversationId(list[0].id)
        } else {
          // Auto create first conversation
          const newConv = await copilotService.createConversation('General Discussion')
          setConversations([newConv])
          setActiveConversationId(newConv.id)
        }
      } catch (err) {
        toast.error('Could not load conversations')
      } finally {
        setLoadingConversations(false)
      }
    }
    fetchConversations()
  }, [])

  // Load messages whenever activeConversationId changes
  useEffect(() => {
    if (!activeConversationId) return
    async function loadActiveConversation() {
      try {
        setLoadingMessages(true)
        const fullConv = await copilotService.getConversation(activeConversationId!)
        setMessages(fullConv.messages || [])
      } catch (err) {
        toast.error('Could not load conversation history')
      } finally {
        setLoadingMessages(false)
      }
    }
    loadActiveConversation()
  }, [activeConversationId])

  useEffect(() => {
    scrollToBottom()
  }, [messages, sending])

  const handleCreateNewConversation = async () => {
    try {
      const newConv = await copilotService.createConversation('New Conversation')
      setConversations((prev) => [newConv, ...prev])
      setActiveConversationId(newConv.id)
      setMessages([])
    } catch {
      toast.error('Failed to create new conversation')
    }
  }

  const handleSendMessage = async (customPrompt?: string) => {
    const textToSend = customPrompt || inputContent
    if (!textToSend.trim() || !activeConversationId || sending) return

    const tempUserMsg: CopilotMessage = {
      id: `temp-${Date.now()}`,
      conversation_id: activeConversationId,
      role: 'user',
      raw_content: textToSend,
      created_at: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, tempUserMsg])
    setInputContent('')
    setSending(true)

    if (copilotVersion === 'v2') {
      setV2Progress({ type: 'STARTED', message: 'Analiz başlatılıyor…' })
      try {
        const assistantMsg = await copilotService.sendV2Message(
          activeConversationId,
          textToSend,
          (event) => setV2Progress(event),
        )
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== tempUserMsg.id),
          tempUserMsg,
          assistantMsg,
        ])
      } catch (err: any) {
        toast.error(err?.message || 'Copilot V2 yanıt veremedi.')
      } finally {
        setSending(false)
        setV2Progress(null)
      }
    } else {
      try {
        const result = await copilotService.sendMessage(activeConversationId, textToSend)
        const assistantMsg = result.message || (result as any).data?.message
        setMessages((prev) => [...prev.filter((m) => m.id !== tempUserMsg.id), tempUserMsg, assistantMsg])
      } catch (err) {
        toast.error('Failed to receive response from Copilot')
      } finally {
        setSending(false)
      }
    }
  }

  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null)
  const [uploadingFile, setUploadingFile] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file || !activeConversationId) return

    setUploadingFile(true)
    try {
      const result = await copilotService.uploadImportFile(activeConversationId, file)
      const assistantMsg = result.message || (result as any).data?.message
      if (assistantMsg) {
        setMessages((prev) => [...prev, assistantMsg])
      }
      toast.success(`${file.name} başarıyla ayrıştırıldı.`)
    } catch (err: any) {
      toast.error(err?.response?.data?.message || err?.message || 'Dosya yükleme başarısız oldu.')
    } finally {
      setUploadingFile(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleResolveImportItem = async (
    batchId: string,
    itemId: string,
    resolution: {
      quantity?: number
      average_cost?: number
      action_resolution?: ActionResolutionType
      selected_instrument_id?: string
    }
  ) => {
    try {
      const updatedBatch = await copilotService.resolveImportItem(batchId, itemId, resolution)
      setMessages((prev) =>
        prev.map((m) => {
          if (m.structured_metadata?.import_batch?.id === batchId) {
            return {
              ...m,
              structured_metadata: {
                ...m.structured_metadata,
                import_batch: updatedBatch,
              },
            }
          }
          return m
        })
      )
      toast.success('Varlık kararı güncellendi.')
    } catch (err: any) {
      toast.error(err?.response?.data?.message || err?.message || 'Kalem güncellenemedi.')
    }
  }

  const handleConfirmProposal = async (proposalId: string, messageId: string, confirmationText?: string) => {
    if (actionLoadingId) return
    setActionLoadingId(proposalId)
    try {
      const res = await copilotService.confirmProposal(proposalId, undefined, confirmationText || 'CONFIRM')
      const updatedProp = res.proposal || (res as any).data || res
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id === messageId) {
            const currentBatch = m.structured_metadata?.import_batch
            return {
              ...m,
              structured_metadata: {
                ...m.structured_metadata,
                proposal: updatedProp,
                import_batch: currentBatch
                  ? { ...currentBatch, status: 'APPLIED' }
                  : undefined,
              },
            }
          }
          return m
        })
      )
      toast.success('İşlem başarıyla uygulandı!')
    } catch (err: any) {
      toast.error(err?.message || 'İşlem uygulanamadı.')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleCancelProposal = async (proposalId: string, messageId: string) => {
    setActionLoadingId(proposalId)
    try {
      const res = await copilotService.cancelProposal(proposalId)
      const updatedProp = (res as any).proposal || (res as any).data || res
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id === messageId) {
            const currentBatch = m.structured_metadata?.import_batch
            return {
              ...m,
              structured_metadata: {
                ...m.structured_metadata,
                proposal: updatedProp,
                import_batch: currentBatch
                  ? { ...currentBatch, status: 'CANCELLED' }
                  : undefined,
              },
            }
          }
          return m
        })
      )
      toast.info('İşlem önerisi iptal edildi.')
    } catch (err: any) {
      toast.error(err?.message || 'İptal işlemi başarısız oldu.')
    } finally {
      setActionLoadingId(null)
    }
  }

  return (
    <AppShell>
      <div className="flex h-[calc(100vh-6rem)] flex-col gap-4 p-4 md:p-6">
        <PageHeader
          title="PortfolioMind Copilot"
          description="Conversational financial core with context provenance and objective thesis analysis"
          actions={
            <div className="flex items-center rounded-lg bg-card/90 p-1 border border-border/60 text-xs shadow-sm">
              <button
                type="button"
                onClick={() => handleVersionChange('v1')}
                className={cn(
                  'rounded-md px-3 py-1 font-medium transition-all cursor-pointer',
                  copilotVersion === 'v1'
                    ? 'bg-muted text-foreground font-semibold shadow-xs'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                Copilot V1
              </button>
              <button
                type="button"
                onClick={() => handleVersionChange('v2')}
                className={cn(
                  'flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition-all cursor-pointer',
                  copilotVersion === 'v2'
                    ? 'bg-teal-500/20 text-teal-400 border border-teal-500/40 font-semibold shadow-xs'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <Sparkles className="size-3 text-teal-400" />
                V2 Beta (Codex)
              </button>
            </div>
          }
        />

        <div className="grid flex-1 grid-cols-1 gap-4 overflow-hidden md:grid-cols-4">
          {/* Left panel: Conversations list */}
          <Card className="flex flex-col overflow-hidden border-border/40 bg-card/60 md:col-span-1">
            <div className="flex items-center justify-between border-b border-border/40 p-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Sessions
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCreateNewConversation}
                className="h-7 text-xs"
              >
                <Plus className="mr-1 size-3.5" /> New
              </Button>
            </div>
            <div className="flex-1 space-y-1 overflow-y-auto p-2">
              {loadingConversations ? (
                <div className="space-y-2 p-2">
                  <Skeleton className="h-9 w-full" />
                  <Skeleton className="h-9 w-full" />
                  <Skeleton className="h-9 w-full" />
                </div>
              ) : conversations.length === 0 ? (
                <div className="p-4 text-center text-xs text-muted-foreground">
                  No sessions yet
                </div>
              ) : (
                conversations.map((conv) => (
                  <button
                    key={conv.id}
                    onClick={() => setActiveConversationId(conv.id)}
                    className={cn(
                      'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-medium transition-colors',
                      activeConversationId === conv.id
                        ? 'bg-teal-500/15 text-teal-400 border border-teal-500/30'
                        : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
                    )}
                  >
                    <MessageSquare className="size-3.5 shrink-0" />
                    <span className="truncate">{conv.title || 'Untitled Session'}</span>
                  </button>
                ))
              )}
            </div>
          </Card>

          {/* Right main panel: Conversation thread */}
          <Card className="flex flex-col overflow-hidden border-border/40 bg-card/60 md:col-span-3">
            {/* Messages area */}
            <div className="flex-1 space-y-4 overflow-y-auto p-4 md:p-6">
              {loadingMessages ? (
                <div className="space-y-4">
                  <div className="flex gap-3">
                    <Skeleton className="size-8 rounded-full" />
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-48" />
                      <Skeleton className="h-16 w-80" />
                    </div>
                  </div>
                </div>
              ) : messages.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center space-y-4 text-center">
                  <div className="flex size-12 items-center justify-center rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
                    <Bot className="size-6" />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-foreground">PortfolioMind Copilot</h3>
                    <p className="mt-1 max-w-sm text-xs text-muted-foreground">
                      Ask about portfolio risks, thesis tracking, or explore hypothetical allocation changes.
                    </p>
                  </div>
                  <div className="flex flex-wrap justify-center gap-2 pt-2 max-w-md">
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs bg-muted/40 hover:bg-muted"
                      onClick={() => handleSendMessage('Where are my biggest portfolio risks?')}
                    >
                      Where are my biggest portfolio risks?
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs bg-muted/40 hover:bg-muted"
                      onClick={() => handleSendMessage('Would increasing crypto to 15% make sense?')}
                    >
                      Would increasing crypto to 15% make sense?
                    </Button>
                  </div>
                </div>
              ) : (
                messages.map((msg) => {
                  const isUser = msg.role === 'user'
                  const contextUsed: ContextProvenanceItem[] =
                    msg.structured_metadata?.context_used || []
                  const responseType = msg.structured_metadata?.response_type
                  const missingFields = msg.structured_metadata?.missing_fields

                  return (
                    <div
                      key={msg.id}
                      className={cn(
                        'flex gap-3',
                        isUser ? 'justify-end' : 'justify-start',
                      )}
                    >
                      {!isUser && (
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-teal-500/15 border border-teal-500/30 text-teal-400">
                          <Bot className="size-4" />
                        </div>
                      )}

                      <div
                        className={cn(
                          'max-w-[85%] rounded-xl px-4 py-3 text-sm md:max-w-[75%]',
                          isUser
                            ? 'bg-teal-600 text-white shadow-sm'
                            : 'bg-muted/60 text-foreground border border-border/50',
                        )}
                      >
                        {/* Response kind pill */}
                        {!isUser && responseType === 'NEEDS_INPUT' && (
                          <div className="mb-2">
                            <Badge variant="outline" className="text-[10px] border-amber-500/40 text-amber-400 bg-amber-500/10">
                              Needs Information
                            </Badge>
                          </div>
                        )}
                        {!isUser && responseType === 'ACTION_INTENT' && (
                          <div className="mb-2">
                            <Badge variant="outline" className="text-[10px] border-teal-500/40 text-teal-400 bg-teal-500/10">
                              Action Recognized (Phase 2 Preview)
                            </Badge>
                          </div>
                        )}

                        <div className="whitespace-pre-wrap leading-relaxed">{msg.raw_content}</div>

                        {/* Missing fields notification */}
                        {missingFields && missingFields.length > 0 && (
                          <div className="mt-2 text-xs text-amber-300">
                            Required fields: {missingFields.join(', ')}
                          </div>
                        )}

                        {/* Phase 3 Portfolio Import Card */}
                        {msg.structured_metadata?.import_batch && (
                          <PortfolioImportCard
                            batch={msg.structured_metadata.import_batch}
                            proposal={msg.structured_metadata.proposal}
                            onConfirm={(pId, text) => handleConfirmProposal(pId, msg.id, text)}
                            onCancel={(pId) => handleCancelProposal(pId, msg.id)}
                            onResolveItem={handleResolveImportItem}
                            loading={actionLoadingId === msg.structured_metadata.proposal?.id}
                          />
                        )}

                        {/* Phase 3 Action Proposal Card (only if not an import batch) */}
                        {msg.structured_metadata?.proposal && !msg.structured_metadata?.import_batch && (
                          <ActionProposalCard
                            proposal={msg.structured_metadata.proposal}
                            onConfirm={(pId, text) => handleConfirmProposal(pId, msg.id, text)}
                            onCancel={(pId) => handleCancelProposal(pId, msg.id)}
                            loading={actionLoadingId === msg.structured_metadata.proposal?.id}
                          />
                        )}

                        {/* Phase 3.2 Portfolio Simulation Card */}
                        {msg.structured_metadata?.simulation && (
                          <SimulationCard simulation={msg.structured_metadata.simulation} />
                        )}



                        {/* Compact Context Used Section */}
                        {!isUser && contextUsed.length > 0 && (
                          <div className="mt-3 border-t border-border/40 pt-2.5">
                            <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
                              <Database className="size-3 text-teal-400" />
                              <span>Context used:</span>
                            </div>
                            <div className="mt-1.5 flex flex-wrap gap-1.5">
                              {contextUsed.map((item, idx) => (
                                <span
                                  key={idx}
                                  className="inline-flex items-center gap-1 rounded bg-background/80 px-2 py-0.5 text-[10px] text-muted-foreground border border-border/40"
                                >
                                  {item.title}
                                  {item.freshness && (
                                    <span className="text-[9px] text-teal-400/80 font-mono">
                                      ({item.freshness.toLowerCase()})
                                    </span>
                                  )}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* External Evidence Sources */}
                        {!isUser && (
                          <ExternalSourcesSection
                            sources={msg.structured_metadata?.external_sources || msg.external_sources}
                          />
                        )}

                        {/* V2 Diagnostics Telemetry */}
                        {!isUser && msg.structured_metadata?.trace && (
                          <V2DiagnosticsSection trace={msg.structured_metadata.trace} />
                        )}
                      </div>

                      {isUser && (
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-slate-700 border border-slate-600 text-slate-200">
                          <UserIcon className="size-4" />
                        </div>
                      )}
                    </div>
                  )
                })
              )}

              {/* Sending / Thinking state */}
              {sending && (
                <div className="flex gap-3 justify-start animate-in fade-in-50">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-teal-500/15 border border-teal-500/30 text-teal-400">
                    <Bot className="size-4 animate-pulse" />
                  </div>
                  <div className="flex flex-col gap-1 rounded-xl bg-muted/60 px-4 py-3 text-xs text-muted-foreground border border-border/50 max-w-md">
                    <div className="flex items-center gap-2">
                      <Loader2 className="size-3.5 animate-spin text-teal-400 shrink-0" />
                      <span className="font-medium text-foreground">
                        {copilotVersion === 'v2'
                          ? v2Progress?.message || 'Analiz başlatılıyor…'
                          : 'Analyzing portfolio state & reasoning...'}
                      </span>
                    </div>
                    {copilotVersion === 'v2' && v2Progress?.target_profile && (
                      <span className="text-[11px] text-teal-400/90 pl-5.5">
                        {v2Progress.target_profile === 'DEEP'
                          ? 'Kapsamlı değerlendirme için derin analiz modeline geçildi (biraz sürebilir)...'
                          : 'Detaylı değerlendirme için dengeli analiz modeline geçildi...'}
                      </span>
                    )}
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Message input bar */}
            <div className="border-t border-border/40 p-3 bg-card/40">
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  handleSendMessage()
                }}
                className="flex items-center gap-2"
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  accept=".csv,text/csv,image/png,image/jpeg,image/webp"
                  className="hidden"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={uploadingFile || sending || !activeConversationId}
                  onClick={() => fileInputRef.current?.click()}
                  className="h-9 px-2.5 text-muted-foreground hover:text-foreground shrink-0"
                  title="CSV veya Ekran Görüntüsü Yükle"
                >
                  {uploadingFile ? (
                    <Loader2 className="size-4 animate-spin text-teal-400" />
                  ) : (
                    <Paperclip className="size-4" />
                  )}
                </Button>
                <Input
                  value={inputContent}
                  onChange={(e) => setInputContent(e.target.value)}
                  placeholder={
                    copilotVersion === 'v2'
                      ? 'Ask PortfolioMind Copilot V2 (Codex Engine)...'
                      : 'Ask PortfolioMind Copilot...'
                  }
                  disabled={sending || !activeConversationId}
                  className="flex-1 bg-background/80 text-sm focus-visible:ring-teal-500"
                />
                <Button
                  type="submit"
                  size="sm"
                  disabled={sending || !inputContent.trim() || !activeConversationId}
                  className="bg-teal-600 hover:bg-teal-500 text-white shrink-0"
                >
                  {sending ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <>
                      <Send className="size-3.5 mr-1.5" />
                      Send
                    </>
                  )}
                </Button>
              </form>
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  )
}
