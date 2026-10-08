import { useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle,
  FileSpreadsheet,
  HelpCircle,
  Image as ImageIcon,
  Loader2,
  Sparkles,
  XCircle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type {
  ActionProposal,
  ActionResolutionType,
  PortfolioImportBatch,
  PortfolioImportItem,
} from '@/types/copilot'

interface PortfolioImportCardProps {
  batch: PortfolioImportBatch
  proposal?: ActionProposal | null
  onConfirm?: (proposalId: string, confirmationText?: string) => Promise<void>
  onCancel?: (proposalId: string) => Promise<void>
  onResolveItem?: (
    batchId: string,
    itemId: string,
    resolution: {
      quantity?: number
      average_cost?: number
      action_resolution?: ActionResolutionType
      selected_instrument_id?: string
    }
  ) => Promise<void>
  loading?: boolean
}

export function PortfolioImportCard({
  batch,
  proposal,
  onConfirm,
  onCancel,
  onResolveItem,
  loading = false,
}: PortfolioImportCardProps) {
  const [confirmationText, setConfirmationText] = useState('')
  const [resolvingItemId, setResolvingItemId] = useState<string | null>(null)
  const [editState, setEditState] = useState<Record<string, {
    quantity?: string
    cost?: string
    action?: ActionResolutionType
  }>>({})

  const handleEditChange = (
    itemId: string,
    field: 'quantity' | 'cost' | 'action',
    value: string
  ) => {
    setEditState((prev) => ({
      ...prev,
      [itemId]: {
        ...prev[itemId],
        [field]: value,
      },
    }))
  }

  const handleSaveItem = async (item: PortfolioImportItem) => {
    if (!onResolveItem) return
    const current = editState[item.id] || {}
    const parsedQty = current.quantity !== undefined ? parseFloat(current.quantity) : item.quantity ?? undefined
    const parsedCost = current.cost !== undefined ? parseFloat(current.cost) : item.average_cost ?? undefined
    const selectedAction = current.action || (item.action_resolution as ActionResolutionType) || undefined

    setResolvingItemId(item.id)
    try {
      await onResolveItem(batch.id, item.id, {
        quantity: isNaN(parsedQty as number) ? undefined : parsedQty,
        average_cost: isNaN(parsedCost as number) ? undefined : parsedCost,
        action_resolution: selectedAction,
      })
    } finally {
      setResolvingItemId(null)
    }
  }

  const getSourceIcon = (source: string) => {
    switch (source) {
      case 'CSV':
        return <FileSpreadsheet className="size-3.5 text-emerald-400" />
      case 'SCREENSHOT':
        return <ImageIcon className="size-3.5 text-blue-400" />
      default:
        return <Sparkles className="size-3.5 text-teal-400" />
    }
  }

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'CREATE_OPENING_POSITION':
        return (
          <Badge variant="outline" className="border-emerald-500/40 bg-emerald-500/10 text-emerald-400 text-[10px]">
            Yeni Açılış Pozisyonu
          </Badge>
        )
      case 'UPDATE_EXISTING_OPENING_POSITION':
        return (
          <Badge variant="outline" className="border-blue-500/40 bg-blue-500/10 text-blue-400 text-[10px]">
            Pozisyonu Güncelle
          </Badge>
        )
      case 'ADD_TO_EXISTING_POSITION':
        return (
          <Badge variant="outline" className="border-cyan-500/40 bg-cyan-500/10 text-cyan-400 text-[10px]">
            Pozisyona İlave Et
          </Badge>
        )
      case 'SKIP':
        return (
          <Badge variant="outline" className="border-muted bg-muted/20 text-muted-foreground text-[10px]">
            Atlandı
          </Badge>
        )
      case 'NEEDS_REVIEW':
        return (
          <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-400 text-[10px]">
            İnceleme Bekliyor
          </Badge>
        )
      case 'AMBIGUOUS':
        return (
          <Badge variant="outline" className="border-orange-500/40 bg-orange-500/10 text-orange-400 text-[10px]">
            Karar Gerekli
          </Badge>
        )
      case 'INVALID':
        return (
          <Badge variant="outline" className="border-red-500/40 bg-red-500/10 text-red-400 text-[10px]">
            Geçersiz
          </Badge>
        )
      default:
        return (
          <Badge variant="outline" className="text-[10px]">
            {action}
          </Badge>
        )
    }
  }

  const hasPendingIssues = batch.items.some(
    (i) => (i.intended_action !== 'SKIP' && i.missing_fields.length > 0) || i.intended_action === 'NEEDS_REVIEW' || i.intended_action === 'AMBIGUOUS' || i.intended_action === 'INVALID'
  )

  const isConfirmedOrApplied = batch.status === 'APPLIED' || batch.status === 'CONFIRMED' || proposal?.status === 'APPLIED'
  const isCancelled = batch.status === 'CANCELLED' || proposal?.status === 'CANCELLED' || proposal?.status === 'EXPIRED' || proposal?.status === 'FAILED'

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-border/80 bg-background/95 shadow-md">
      <div className="px-3.5 py-2 text-sm text-muted-foreground">Maliyet bilinmiyorsa kâr/zarar hesaplanmaz. Görsel ayrıştırma sağlayıcısı henüz bağlı değil; CSV veya metin kullanın.</div>
      {!isConfirmedOrApplied && !isCancelled && <Input aria-label="Strong confirmation" placeholder="Onaylamak için IMPORT yazın" value={confirmationText} onChange={(e) => setConfirmationText(e.target.value)} disabled={loading} />}
      {batch.errors.map((error) => <p key={error} role="alert">{error}</p>)}
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 bg-muted/30 px-3.5 py-2.5">
        <div className="flex items-center gap-2">
          {getSourceIcon(batch.source_type)}
          <span className="text-xs font-semibold text-foreground">
            Portföy İçe Aktarım Taslağı ({batch.source_type})
          </span>
          <Badge variant="outline" className="text-[10px] uppercase font-mono">
            {batch.items.length} Kalem
          </Badge>
        </div>

        <div className="flex items-center gap-1.5">
          {batch.status === 'READY_FOR_CONFIRMATION' && (
            <Badge variant="outline" className="border-teal-500/40 bg-teal-500/10 text-teal-400 text-[10px]">
              Onay Bekliyor
            </Badge>
          )}
          {batch.status === 'DRAFT' && (
            <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-400 text-[10px]">
              Taslak / İnceleme Gerekli
            </Badge>
          )}
          {batch.status === 'APPLIED' && (
            <Badge variant="outline" className="border-emerald-500/50 bg-emerald-500/15 text-emerald-400 text-[10px]">
              Uygulandı
            </Badge>
          )}
          {batch.status === 'CANCELLED' && (
            <Badge variant="outline" className="border-muted bg-muted/20 text-muted-foreground text-[10px]">
              İptal Edildi
            </Badge>
          )}
        </div>
      </div>

      {/* Warnings & Global Notices */}
      {batch.warnings && batch.warnings.length > 0 && (
        <div className="border-b border-border/40 bg-amber-500/5 p-2.5 text-xs text-amber-300">
          {batch.warnings.map((w, idx) => (
            <div key={idx} className="flex items-center gap-1.5">
              <AlertTriangle className="size-3.5 shrink-0 text-amber-400" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      {/* Items List */}
      <div className="divide-y divide-border/40">
        {batch.items.map((item) => {
          const itemEdit = editState[item.id] || {}
          const needsAttention =
            item.intended_action === 'NEEDS_REVIEW' ||
            item.intended_action === 'AMBIGUOUS' ||
            item.intended_action === 'INVALID'

          return (
            <div key={item.id} className="p-3 text-xs transition-colors hover:bg-muted/20">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-foreground">
                    {item.symbol || item.name}
                  </span>
                  {item.symbol && item.name && item.name !== item.symbol && (
                    <span className="text-[11px] text-muted-foreground">({item.name})</span>
                  )}
                  <Badge variant="secondary" className="text-[9px] px-1.5 py-0">
                    {item.asset_type}
                  </Badge>
                </div>
                <div>{getActionBadge(item.intended_action)}</div>
              </div>

              {/* Quantities & Values */}
              <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-muted-foreground sm:grid-cols-4">
                <div>
                  <span className="text-muted-foreground/80">Mevcut Portföy: </span>
                  <span className="font-mono font-medium text-foreground">
                    {item.existing_quantity != null ? item.existing_quantity : '0 (Yeni)'}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground/80">İçe Aktarılan Miktar: </span>
                  <span className="font-mono font-medium text-foreground">
                    {item.quantity != null ? item.quantity : (
                      <span className="text-amber-400 font-semibold">Eksik</span>
                    )}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground/80">Birim Maliyet: </span>
                  <span className="font-mono font-medium text-foreground">
                    {item.average_cost != null
                      ? `${item.average_cost} ${item.currency || 'USD'}`
                      : 'Bilinmiyor (0 kâr/zarar)'}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground/80">Kaynak Metin: </span>
                  <span className="truncate italic font-mono text-[10px] text-muted-foreground">
                    {item.raw_input || '-'}
                  </span>
                </div>
              </div>

              {/* Warnings / Missing fields on item */}
              {item.warnings && item.warnings.length > 0 && (
                <div className="mt-2 space-y-1">
                  {item.warnings.map((w, wIdx) => (
                    <div key={wIdx} className="flex items-center gap-1.5 text-[11px] text-amber-300">
                      <AlertCircle className="size-3 shrink-0 text-amber-400" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Inline Resolution Controls */}
              {needsAttention && !isConfirmedOrApplied && !isCancelled && (
                <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-2.5">
                  <div className="mb-2 text-[11px] font-semibold text-amber-400">
                    İşlem Kararı ve Eksik Bilgi Tamamlama:
                  </div>

                  {/* If Ambiguity with Existing Holding */}
                  {item.existing_quantity != null && (
                    <div className="mb-2.5 space-y-1.5">
                      <label className="text-[11px] text-muted-foreground font-medium">
                        Mevcut ({item.existing_quantity}) pozisyon ile nasıl birleştirilsin?
                      </label>
                      <div className="flex flex-wrap gap-1.5">
                        <Button
                          type="button"
                          size="sm"
                          variant={
                            (itemEdit.action || item.action_resolution) === 'REPLACE_OPENING_STATE'
                              ? 'default'
                              : 'outline'
                          }
                          className="h-7 text-[11px] px-2"
                          onClick={() => handleEditChange(item.id, 'action', 'REPLACE_OPENING_STATE')}
                        >
                          Pozisyonu Güncelle ({item.quantity ?? 'Yeni Değer'})
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant={
                            (itemEdit.action || item.action_resolution) === 'ADD_TO_EXISTING'
                              ? 'default'
                              : 'outline'
                          }
                          className="h-7 text-[11px] px-2"
                          onClick={() => handleEditChange(item.id, 'action', 'ADD_TO_EXISTING')}
                        >
                          Mevcut Üzerine Ekle (+{item.quantity ?? 'Ekle'})
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant={
                            (itemEdit.action || item.action_resolution) === 'SKIP'
                              ? 'default'
                              : 'outline'
                          }
                          className="h-7 text-[11px] px-2 text-muted-foreground"
                          onClick={() => handleEditChange(item.id, 'action', 'SKIP')}
                        >
                          Bu Varlığı Atla
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Missing or editable quantity / cost */}
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="flex items-center gap-1">
                      <span className="text-[11px] text-muted-foreground">Miktar:</span>
                      <Input
                        type="number"
                        step="any"
                        placeholder="Adet"
                        defaultValue={item.quantity ?? ''}
                        onChange={(e) => handleEditChange(item.id, 'quantity', e.target.value)}
                        className="h-7 w-24 text-xs"
                      />
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-[11px] text-muted-foreground">Birim Maliyet:</span>
                      <Input
                        type="number"
                        step="any"
                        placeholder="Opsiyonel"
                        defaultValue={item.average_cost ?? ''}
                        onChange={(e) => handleEditChange(item.id, 'cost', e.target.value)}
                        className="h-7 w-28 text-xs"
                      />
                    </div>
                    <Button
                      size="sm"
                      className="h-7 text-xs bg-teal-600 hover:bg-teal-500 text-white"
                      disabled={resolvingItemId === item.id}
                      onClick={() => handleSaveItem(item)}
                    >
                      {resolvingItemId === item.id ? (
                        <Loader2 className="size-3 animate-spin mr-1" />
                      ) : (
                        <Check className="size-3 mr-1" />
                      )}
                      Kaydet
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Footer / Actions */}
      <div className="border-t border-border/60 bg-muted/20 p-3">
        {hasPendingIssues && !isConfirmedOrApplied && !isCancelled && (
          <div className="mb-2.5 flex items-center gap-1.5 text-xs text-amber-400">
            <HelpCircle className="size-4 shrink-0 text-amber-400" />
            <span>
              Portföye aktarmadan önce yukarıdaki inceleme veya karar bekleyen kalemleri çözün veya atlayın.
            </span>
          </div>
        )}

        {!isConfirmedOrApplied && !isCancelled && proposal && (
          <div className="flex items-center justify-between gap-2">
            <div className="text-[11px] text-muted-foreground">
              {batch.ready_count} hazır kalem portföye açılış pozisyonu olarak aktarılacak.
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                className="h-8 text-xs bg-teal-600 hover:bg-teal-500 text-white font-medium shadow-sm disabled:opacity-50"
                disabled={loading || hasPendingIssues || batch.errors.length > 0 || batch.status !== 'READY_FOR_CONFIRMATION'}
                onClick={() => confirmationText ? onConfirm?.(proposal.id, confirmationText) : onConfirm?.(proposal.id)}
              >
                {loading ? (
                  <Loader2 className="size-3.5 animate-spin mr-1.5" />
                ) : (
                  <CheckCircle className="size-3.5 mr-1.5 text-teal-200" />
                )}
                Onayla ve Portföye Aktar
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-8 text-xs text-muted-foreground hover:text-foreground"
                disabled={loading}
                onClick={() => onCancel?.(proposal.id)}
              >
                <XCircle className="size-3.5 mr-1 text-muted-foreground" />
                İptal Et
              </Button>
            </div>
          </div>
        )}

        {isConfirmedOrApplied && (
          <div className="flex items-center gap-2 text-xs font-medium text-emerald-400">
            <CheckCircle className="size-4 text-emerald-400" />
            <span>Portföy başarıyla güncellendi ve açılış pozisyonları oluşturuldu.</span>
          </div>
        )}

        {isCancelled && (
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <XCircle className="size-4 text-muted-foreground" />
            <span>İçe aktarım işlemi iptal edildi.</span>
          </div>
        )}
      </div>
    </div>
  )
}
