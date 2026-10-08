import React from 'react'
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle,
  Clock,
  Eye,
  FileText,
  Info,
  Loader2,
  Sparkles,
  XCircle,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { ActionProposal } from '@/types/copilot'
import { cn } from '@/utils/cn'

interface ActionProposalCardProps {
  proposal: ActionProposal
  onConfirm: (proposalId: string, confirmationText?: string) => void
  onCancel: (proposalId: string) => void
  loading?: boolean
}

export const ActionProposalCard: React.FC<ActionProposalCardProps> = ({
  proposal,
  onConfirm,
  onCancel,
  loading = false,
}) => {
  const isPending =
    proposal.status === 'PENDING' ||
    proposal.status === 'READY_FOR_CONFIRMATION' ||
    proposal.status === 'DRAFT'
  const isApplied = proposal.status === 'APPLIED' || proposal.status === 'EXECUTED'
  const isCancelled = proposal.status === 'CANCELLED'
  const isStale = proposal.status === 'STALE'
  const isExpired = proposal.status === 'EXPIRED'
  const isFailed = proposal.status === 'FAILED'

  const actionType = proposal.action_type || 'UNKNOWN'
  const params = proposal.parameters || {}
  const impact = proposal.expected_impact || {}
  const warnings = proposal.warnings || []

  // Icon & label based on action type
  const getActionMetadata = () => {
    if (actionType === 'TRANSACTION_RECORD' || actionType.includes('TRANSACTION') || actionType === 'BUY' || actionType === 'SELL') {
      const isBuy = params.transaction_type === 'BUY' || actionType.includes('BUY')
      return {
        icon: isBuy ? ArrowDownRight : ArrowUpRight,
        iconColor: isBuy ? 'text-teal-400' : 'text-amber-400',
        label: isBuy ? 'PORTFÖY ALIŞ KAYDI' : 'PORTFÖY SATIŞ KAYDI',
      }
    }
    if (actionType === 'WATCHLIST_CHANGE' || actionType.includes('WATCHLIST')) {
      return {
        icon: Eye,
        iconColor: 'text-sky-400',
        label: 'İZLEME LİSTESİ EYLEMİ',
      }
    }
    if (actionType === 'DECISION_NOTE' || actionType.includes('JOURNAL')) {
      return {
        icon: FileText,
        iconColor: 'text-violet-400',
        label: 'KARAR GÜNLÜĞÜ NOTU',
      }
    }
    return {
      icon: Sparkles,
      iconColor: 'text-teal-400',
      label: actionType.replace(/_/g, ' '),
    }
  }

  const { icon: ActionIcon, iconColor, label: actionLabel } = getActionMetadata()

  return (
    <div className="mt-3 rounded-xl border border-border/80 bg-background/95 p-4 shadow-sm space-y-3 transition-all">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b border-border/40 pb-2.5">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-lg bg-muted/60 border border-border/50">
            <ActionIcon className={cn('size-4', iconColor)} />
          </div>
          <div>
            <span className="text-xs font-semibold tracking-wider text-foreground">
              {actionLabel}
            </span>
          </div>
        </div>

        {/* Status Badge */}
        <Badge
          variant="outline"
          className={cn(
            'text-[10px] uppercase font-semibold tracking-wider px-2 py-0.5',
            isPending && 'border-amber-500/50 text-amber-400 bg-amber-500/10',
            isApplied && 'border-teal-500/50 text-teal-400 bg-teal-500/10',
            isCancelled && 'border-muted text-muted-foreground bg-muted/20',
            isStale && 'border-orange-500/50 text-orange-400 bg-orange-500/10',
            isExpired && 'border-muted text-muted-foreground bg-muted/20',
            isFailed && 'border-red-500/50 text-red-400 bg-red-500/10'
          )}
        >
          {isPending && 'Onay Bekliyor'}
          {isApplied && 'Uygulandı'}
          {isCancelled && 'İptal Edildi'}
          {isStale && 'Geçersiz (STALE)'}
          {isExpired && 'Süresi Doldu'}
          {isFailed && 'Başarısız'}
        </Badge>
      </div>

      {/* Human Readable Summary */}
      <div className="text-xs font-medium text-foreground leading-relaxed">
        {proposal.human_readable_summary}
      </div>

      {/* Action Specific Details / Expected Impact */}
      {impact && Object.keys(impact).length > 0 && (
        <div className="rounded-lg bg-muted/40 p-2.5 text-[11px] grid grid-cols-2 gap-2 border border-border/40">
          {impact.previous_quantity !== undefined && impact.new_quantity !== undefined && (
            <div>
              <span className="text-muted-foreground">Pozisyon: </span>
              <span className="font-mono font-medium text-foreground">
                {impact.previous_quantity} → {impact.new_quantity}
              </span>
            </div>
          )}

          {impact.total_amount !== undefined && (
            <div>
              <span className="text-muted-foreground">İşlem Tutarı: </span>
              <span className="font-mono font-medium text-foreground">
                {Number(impact.total_amount).toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}{' '}
                {impact.currency || params.currency || 'TRY'}
              </span>
            </div>
          )}

          {impact.cash_delta !== undefined && (
            <div>
              <span className="text-muted-foreground">Nakit Etkisi: </span>
              <span
                className={cn(
                  'font-mono font-medium',
                  impact.cash_delta < 0 ? 'text-red-400' : 'text-teal-400'
                )}
              >
                {impact.cash_delta > 0 ? '+' : ''}
                {Number(impact.cash_delta).toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}{' '}
                {impact.currency || params.currency || 'TRY'}
              </span>
            </div>
          )}

          {params.transaction_date && (
            <div>
              <span className="text-muted-foreground">Kayıt Tarihi: </span>
              <span className="font-mono text-foreground">{params.transaction_date}</span>
            </div>
          )}

          {(actionType === 'WATCHLIST_CHANGE' || impact.action === 'ADD' || impact.action === 'REMOVE') && impact.action && (
            <div>
              <span className="text-muted-foreground">İzleme Listesi: </span>
              <span className="font-medium text-foreground">
                {impact.action === 'ADD' ? 'Ekle' : 'Çıkar'} ({impact.symbol || params.symbol})
              </span>
            </div>
          )}

          {impact.title && (
            <div className="col-span-2">
              <span className="text-muted-foreground">Not Başlığı: </span>
              <span className="font-medium text-foreground">{impact.title}</span>
            </div>
          )}
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="space-y-1 rounded-lg bg-amber-500/10 p-2.5 text-[11px] text-amber-300 border border-amber-500/20">
          {warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-1.5">
              <AlertTriangle className="size-3.5 text-amber-400 shrink-0 mt-0.5" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      {/* Product Boundary Notice */}
      <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground bg-muted/20 rounded px-2.5 py-1.5 border border-border/30">
        <Info className="size-3 text-teal-400 shrink-0" />
        <span>
          Bu işlem bir borsa/aracı kurum emri değildir; yalnızca PortfolioMind içi portföy kayıtlarınızı günceller.
        </span>
      </div>

      {/* Action Buttons for PENDING */}
      {isPending && (
        <div className="flex items-center gap-2 pt-1 border-t border-border/40">
          <Button
            size="sm"
            className="h-8 text-xs bg-teal-600 hover:bg-teal-500 text-white font-medium shadow-sm transition-colors"
            disabled={loading}
            onClick={() => onConfirm(proposal.id)}
          >
            {loading ? (
              <Loader2 className="size-3.5 animate-spin mr-1.5" />
            ) : (
              <CheckCircle className="size-3.5 mr-1.5 text-teal-200" />
            )}
            Onayla ve Uygula
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-8 text-xs text-muted-foreground hover:text-foreground"
            disabled={loading}
            onClick={() => onCancel(proposal.id)}
          >
            <XCircle className="size-3.5 mr-1 text-muted-foreground" />
            İptal Et
          </Button>
        </div>
      )}

      {/* Finalized Status Indicators */}
      {isApplied && (
        <div className="flex items-center gap-1.5 text-[11px] text-teal-400 font-medium pt-1 border-t border-border/40">
          <CheckCircle className="size-3.5 text-teal-400" />
          <span>İşlem başarıyla doğrulandı ve portföy kayıtlarınıza uygulandı.</span>
        </div>
      )}

      {isCancelled && (
        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground font-medium pt-1 border-t border-border/40">
          <XCircle className="size-3.5 text-muted-foreground" />
          <span>İşlem önerisi iptal edildi. Herhangi bir değişiklik yapılmadı.</span>
        </div>
      )}

      {isStale && (
        <div className="flex items-center gap-1.5 text-[11px] text-orange-400 font-medium pt-1 border-t border-border/40">
          <Clock className="size-3.5 text-orange-400" />
          <span>Portföy bakiyesi değiştiği için öneri bayatladı (STALE) ve iptal edildi.</span>
        </div>
      )}
    </div>
  )
}
