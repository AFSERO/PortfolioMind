import { useEffect, useState } from 'react'
import {
  ArrowRightLeft,
  CheckCircle2,
  Layers,
  Plus,
  Target,
  Trash2,
  Wallet,
} from 'lucide-react'
import { toast } from 'sonner'

import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { financialContextService } from '@/services/financialContextService'
import type {
  FinancialContext,
  FinancialGoal,
  FinancialIntelligenceSummary,
  InvestmentMandate,
  UnassignedResourcesResponse,
} from '@/types/financialContext'

export default function FinancialProfilePage() {
  const [_loading, setLoading] = useState(true)
  const [context, setContext] = useState<FinancialContext | null>(null)
  const [goals, setGoals] = useState<FinancialGoal[]>([])
  const [mandates, setMandates] = useState<InvestmentMandate[]>([])
  const [intel, setIntel] = useState<FinancialIntelligenceSummary | null>(null)
  const [unassigned, setUnassigned] = useState<UnassignedResourcesResponse | null>(null)

  // Edit context form
  const [monthlyIncome, setMonthlyIncome] = useState('')
  const [monthlyExpenses, setMonthlyExpenses] = useState('')
  const [incomeStability, setIncomeStability] = useState('UNKNOWN')
  const [updatingContext, setUpdatingContext] = useState(false)

  // Modals
  const [showGoalModal, setShowGoalModal] = useState(false)
  const [newGoalName, setNewGoalName] = useState('')
  const [newGoalType, setNewGoalType] = useState('HOME_PURCHASE')
  const [newGoalAmount, setNewGoalAmount] = useState('')
  const [newGoalDate, setNewGoalDate] = useState('')
  const [newGoalPriority, setNewGoalPriority] = useState('ESSENTIAL')

  const [showMandateModal, setShowMandateModal] = useState(false)
  const [newMandateName, setNewMandateName] = useState('')
  const [newMandateType, setNewMandateType] = useState('PRESERVATION')
  const [newMandateGoalId, setNewMandateGoalId] = useState<string>('none')
  const [newMandateRisk, setNewMandateRisk] = useState('MODERATE')

  const [showTransferModal, setShowTransferModal] = useState(false)
  const [fromMandateId, setFromMandateId] = useState('')
  const [toMandateId, setToMandateId] = useState('')
  const [transferResourceType, setTransferResourceType] = useState<'ASSET' | 'CASH_ACCOUNT'>('ASSET')
  const [transferAssetId, setTransferAssetId] = useState('')
  const [transferQuantity, setTransferQuantity] = useState('')
  const [transferAmount, setTransferAmount] = useState('')

  const loadData = async () => {
    try {
      setLoading(true)
      const [ctxData, goalsData, mandatesData, intelData, unassignedData] = await Promise.all([
        financialContextService.getFinancialContext(),
        financialContextService.listGoals(),
        financialContextService.listMandates(),
        financialContextService.getFinancialIntelligenceSummary(),
        financialContextService.getUnassignedResources(),
      ])
      setContext(ctxData)
      setGoals(goalsData)
      setMandates(mandatesData)
      setIntel(intelData)
      setUnassigned(unassignedData)

      if (ctxData) {
        setMonthlyIncome(ctxData.monthly_net_income ? String(ctxData.monthly_net_income) : '')
        setMonthlyExpenses(ctxData.monthly_essential_expenses ? String(ctxData.monthly_essential_expenses) : '')
        setIncomeStability(ctxData.income_stability || 'UNKNOWN')
      }
    } catch (err: any) {
      toast.error('Veriler yüklenirken bir hata oluştu.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleSaveContext = async () => {
    try {
      setUpdatingContext(true)
      await financialContextService.updateFinancialContext({
        monthly_net_income: monthlyIncome ? monthlyIncome : null,
        monthly_essential_expenses: monthlyExpenses ? monthlyExpenses : null,
        income_stability: incomeStability as any,
      })
      toast.success('Finansal durum ve nakit akışı güncellendi.')
      await loadData()
    } catch (err: any) {
      toast.error(err.message || 'Güncelleme başarısız oldu.')
    } finally {
      setUpdatingContext(false)
    }
  }

  const handleConfirmContext = async () => {
    try {
      setUpdatingContext(true)
      await financialContextService.confirmFinancialContext()
      toast.success('Finansal profil bilgileri onaylandı.')
      await loadData()
    } catch (err: any) {
      toast.error(err.message || 'Onaylama başarısız oldu.')
    } finally {
      setUpdatingContext(false)
    }
  }

  const handleCreateGoal = async () => {
    if (!newGoalName) {
      toast.error('Lütfen hedef adını girin.')
      return
    }
    try {
      await financialContextService.createGoal({
        name: newGoalName,
        goal_type: newGoalType as any,
        target_amount: newGoalAmount ? Number(newGoalAmount) : null,
        target_date: newGoalDate || null,
        priority: newGoalPriority as any,
      })
      toast.success('Yeni finansal hedef oluşturuldu.')
      setShowGoalModal(false)
      setNewGoalName('')
      setNewGoalAmount('')
      setNewGoalDate('')
      await loadData()
    } catch (err: any) {
      toast.error(err.message || 'Hedef oluşturulamadı.')
    }
  }

  const handleDeleteGoal = async (id: string) => {
    if (!confirm('Bu hedefi silmek istediğinizden emin misiniz? Bağlı mandatler ve sermayeleri korunacaktır.')) {
      return
    }
    try {
      await financialContextService.deleteGoal(id)
      toast.success('Hedef silindi (bağlı mandat sermayeleri korundu).')
      await loadData()
    } catch (err: any) {
      toast.error(err.message || 'Hedef silinemedi.')
    }
  }

  const handleCreateMandate = async () => {
    if (!newMandateName) {
      toast.error('Lütfen mandat adını girin.')
      return
    }
    try {
      await financialContextService.createMandate({
        name: newMandateName,
        mandate_type: newMandateType as any,
        goal_id: newMandateGoalId !== 'none' ? newMandateGoalId : null,
        risk_capacity: newMandateRisk as any,
      })
      toast.success('Yeni yatırım mandati oluşturuldu.')
      setShowMandateModal(false)
      setNewMandateName('')
      await loadData()
    } catch (err: any) {
      toast.error(err.message || 'Mandat oluşturulamadı.')
    }
  }

  const handleTransferCapital = async () => {
    if (!fromMandateId || !toMandateId) {
      toast.error('Lütfen kaynak ve hedef mandatleri seçin.')
      return
    }
    if (fromMandateId === toMandateId) {
      toast.error('Kaynak ve hedef mandat aynı olamaz.')
      return
    }

    try {
      if (transferResourceType === 'ASSET') {
        if (!transferAssetId || !transferQuantity) {
          toast.error('Varlık ve miktar belirtilmelidir.')
          return
        }
        await financialContextService.transferCapital({
          from_mandate_id: fromMandateId,
          to_mandate_id: toMandateId,
          resource_type: 'ASSET',
          asset_id: transferAssetId,
          quantity: transferQuantity,
        })
      } else {
        if (!transferAmount) {
          toast.error('Nakit tutarı belirtilmelidir.')
          return
        }
        // Use user's TRY cash account if available
        const cashAcc = unassigned?.cash_accounts[0]
        await financialContextService.transferCapital({
          from_mandate_id: fromMandateId,
          to_mandate_id: toMandateId,
          resource_type: 'CASH_ACCOUNT',
          cash_account_id: cashAcc?.cash_account_id,
          amount: transferAmount,
        })
      }
      toast.success('Sermaye başarıyla transfer edildi. (Sıfır alım/satım işlemi, vergi/maliyet etkisi yok).')
      setShowTransferModal(false)
      await loadData()
    } catch (err: any) {
      toast.error(err.message || 'Transfer başarısız oldu.')
    }
  }

  const formatMoney = (val?: string | number | null, curr = 'TRY') => {
    if (val === null || val === undefined) return 'Belirtilmedi'
    const num = Number(val)
    if (isNaN(num)) return 'Belirtilmedi'
    return `${num.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${curr}`
  }

  return (
    <AppShell>
      <div className="app-page max-w-6xl space-y-6">
        <PageHeader
          title="Finansal Profil, Hedefler ve Mandatler"
          description="Nakit akışı bağlamı, ilk sınıf finansal hedefler ve sanal sermaye havuzları (mandatler)."
        />

        {/* Intelligence KPI Bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="shadow-card border-border/50">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs">Net Değer</CardDescription>
              <CardTitle className="text-xl font-mono text-primary">
                {formatMoney(intel?.net_worth, intel?.currency)}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              Likidite: {formatMoney(intel?.liquid_net_worth, intel?.currency)}
            </CardContent>
          </Card>

          <Card className="shadow-card border-border/50">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs">Aylık Tasarruf Fazlası</CardDescription>
              <CardTitle className="text-xl font-mono text-emerald-500">
                {formatMoney(intel?.monthly_surplus, intel?.currency)}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              Tasarruf Oranı: {intel?.savings_rate_pct != null ? `%${intel.savings_rate_pct}` : 'Belirtilmedi'}
            </CardContent>
          </Card>

          <Card className="shadow-card border-border/50">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs">Acil Durum Karşılama</CardDescription>
              <CardTitle className="text-xl font-mono text-blue-500">
                {intel?.emergency_coverage_months != null ? `${intel.emergency_coverage_months} Ay` : 'Belirtilmedi'}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              Zorunlu gider karşılama tamponu
            </CardContent>
          </Card>

          <Card className="shadow-card border-border/50">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs">Borç / Gelir (DTI)</CardDescription>
              <CardTitle className="text-xl font-mono text-amber-500">
                {intel?.debt_to_income_pct != null ? `%${intel.debt_to_income_pct}` : 'Belirtilmedi'}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              Aylık asgari borç / net gelir
            </CardContent>
          </Card>
        </div>

        {/* Main Content Tabs */}
        <Tabs defaultValue="goals" className="space-y-4">
          <TabsList className="bg-muted/60 p-1">
            <TabsTrigger value="goals" className="flex items-center gap-2">
              <Target className="size-4" />
              <span>Hedefler & Mandatler ({goals.length})</span>
            </TabsTrigger>
            <TabsTrigger value="cashflow" className="flex items-center gap-2">
              <Wallet className="size-4" />
              <span>Nakit Akışı & Gelir/Gider</span>
            </TabsTrigger>
            <TabsTrigger value="unassigned" className="flex items-center gap-2">
              <Layers className="size-4" />
              <span>Tahsis Edilmemiş Sermaye</span>
            </TabsTrigger>
          </TabsList>

          {/* TAB 1: GOALS & MANDATES */}
          <TabsContent value="goals" className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold">Hedefler ve Yatırım Mandatleri</h3>
                <p className="text-xs text-muted-foreground">
                  Hedefler 'Neden ve Ne Zaman'ı, Mandatler ise 'Nasıl'ı tanımlar.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" onClick={() => setShowTransferModal(true)}>
                  <ArrowRightLeft className="size-4 mr-1.5" />
                  Sanal Transfer
                </Button>
                <Button size="sm" variant="outline" onClick={() => setShowMandateModal(true)}>
                  <Plus className="size-4 mr-1.5" />
                  Yeni Mandat
                </Button>
                <Button size="sm" onClick={() => setShowGoalModal(true)}>
                  <Plus className="size-4 mr-1.5" />
                  Yeni Hedef
                </Button>
              </div>
            </div>

            {goals.length === 0 ? (
              <Card className="p-8 text-center border-dashed">
                <Target className="size-10 mx-auto text-muted-foreground mb-3 opacity-60" />
                <h4 className="text-base font-semibold">Henüz tanımlı bir finansal hedefiniz yok</h4>
                <p className="text-sm text-muted-foreground max-w-md mx-auto mt-1 mb-4">
                  Ev alımı, emeklilik veya acil durum fonu gibi hedeflerinizi belirleyin ve yatırımlarınızı bu hedeflere sanal olarak tahsis edin.
                </p>
                <Button onClick={() => setShowGoalModal(true)}>İlk Hedefinizi Ekleyin</Button>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {goals.map((g) => {
                  const targetAmt = g.target_amount ? Number(g.target_amount) : 0
                  const currentFund = Number(g.current_funding) || 0
                  const ratio = targetAmt > 0 ? Math.min(100, Math.round((currentFund / targetAmt) * 100)) : 0

                  return (
                    <Card key={g.id} className="shadow-card border-border/60">
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <CardTitle className="text-base font-semibold">{g.name}</CardTitle>
                            <CardDescription className="text-xs mt-0.5">
                              {g.goal_type} • {g.priority}
                            </CardDescription>
                          </div>
                          <Badge
                            variant={
                              g.status_assessment === 'FUNDED_NOW'
                                ? 'default'
                                : g.status_assessment === 'ON_TRACK'
                                ? 'secondary'
                                : g.status_assessment === 'SHORTFALL'
                                ? 'destructive'
                                : 'outline'
                            }
                            className="text-[10px]"
                          >
                            {g.status_assessment}
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-3 pb-3">
                        <div className="space-y-1">
                          <div className="flex justify-between text-xs">
                            <span className="text-muted-foreground">Mevcut Fonlama:</span>
                            <span className="font-mono font-medium">
                              {formatMoney(g.current_funding, g.target_currency)} / {formatMoney(g.target_amount, g.target_currency)}
                            </span>
                          </div>
                          {targetAmt > 0 && <Progress value={ratio} className="h-1.5" />}
                        </div>

                        {g.target_date && (
                          <div className="text-xs text-muted-foreground">
                            Hedef Tarih: <span className="font-mono text-foreground">{g.target_date}</span>
                          </div>
                        )}

                        {/* Linked Mandates */}
                        <div className="pt-2 border-t border-border/40 space-y-1.5">
                          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
                            Bağlı Yatırım Mandatleri ({g.mandates?.length || 0})
                          </span>
                          {g.mandates?.length > 0 ? (
                            <div className="space-y-1">
                              {g.mandates.map((m) => (
                                <div key={m.id} className="text-xs bg-muted/40 p-2 rounded flex justify-between items-center">
                                  <div>
                                    <span className="font-medium text-foreground">{m.name}</span>
                                    <span className="text-muted-foreground ml-1.5 text-[10px]">({m.mandate_type})</span>
                                  </div>
                                  <span className="font-mono text-xs text-primary font-medium">
                                    {formatMoney(m.total_assigned_value, 'TRY')}
                                  </span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground italic">Henüz atanmış bir mandat yok.</span>
                          )}
                        </div>
                      </CardContent>
                      <CardFooter className="pt-0 justify-end">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-7 text-muted-foreground hover:text-destructive"
                          onClick={() => handleDeleteGoal(g.id)}
                          title="Hedefi Sil"
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </CardFooter>
                    </Card>
                  )
                })}
              </div>
            )}

            {/* Mandates list & breakdown */}
            <div className="mt-8 space-y-4">
              <h4 className="text-base font-semibold">Tüm Yatırım Mandatleri ({mandates.length})</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {mandates.map((m) => (
                  <Card key={m.id} className="border-border/60">
                    <CardHeader className="pb-2">
                      <div className="flex justify-between items-center">
                        <Badge variant="outline" className="text-[10px]">{m.mandate_type}</Badge>
                        <span className="text-[10px] font-mono text-muted-foreground">{m.risk_capacity}</span>
                      </div>
                      <CardTitle className="text-sm font-semibold">{m.name}</CardTitle>
                    </CardHeader>
                    <CardContent className="text-xs space-y-2">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Toplam Değer:</span>
                        <span className="font-mono font-medium text-primary">{formatMoney(m.total_assigned_value, 'TRY')}</span>
                      </div>
                      <div className="space-y-1">
                        <span className="text-[10px] text-muted-foreground block font-semibold">Tahsis Edilmiş Varlıklar:</span>
                        {m.assignments?.length > 0 ? (
                          m.assignments.map((a) => (
                            <div key={a.id} className="flex justify-between text-[11px] bg-background/50 px-1.5 py-0.5 rounded border border-border/30">
                              <span>{a.resource_symbol || a.resource_name || 'Varlık'}</span>
                              <span className="font-mono">
                                {a.resource_type === 'ASSET' ? `${a.assigned_quantity} Adet` : formatMoney(a.assigned_amount, 'TRY')}
                              </span>
                            </div>
                          ))
                        ) : (
                          <span className="text-[11px] text-muted-foreground italic">Sermaye tahsis edilmedi</span>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          </TabsContent>

          {/* TAB 2: CASH FLOW & CONTEXT */}
          <TabsContent value="cashflow" className="space-y-4">
            <Card className="max-w-2xl border-border/60">
              <CardHeader>
                <CardTitle className="text-base">Aylık Nakit Akışı ve Finansal Bağlam</CardTitle>
                <CardDescription>
                  Gelir ve zorunlu harcama tahminleriniz, acil durum dayanıklılığı ve tasarruf oranı hesaplamalarında kullanılır.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="income">Aylık Net Gelir (TRY)</Label>
                  <Input
                    id="income"
                    type="number"
                    placeholder="Örn: 100000"
                    value={monthlyIncome}
                    onChange={(e) => setMonthlyIncome(e.target.value)}
                  />
                  <p className="text-[11px] text-muted-foreground">
                    Vergi ve kesintiler sonrası ele geçen tahmini net toplam.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="expenses">Aylık Zorunlu Giderler (TRY)</Label>
                  <Input
                    id="expenses"
                    type="number"
                    placeholder="Örn: 65000"
                    value={monthlyExpenses}
                    onChange={(e) => setMonthlyExpenses(e.target.value)}
                  />
                  <p className="text-[11px] text-muted-foreground">
                    Kira, faturalar, asgari borç ödemeleri ve gıda gibi vazgeçilemez harcamalar.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="stability">Gelir İstikrarı</Label>
                  <Select value={incomeStability} onValueChange={setIncomeStability}>
                    <SelectTrigger id="stability">
                      <SelectValue placeholder="Seçiniz" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="PREDICTABLE">Öngörülebilir / Düzenli (Maaşlı vb.)</SelectItem>
                      <SelectItem value="VARIABLE">Değişken (Serbest çalışan, primli vb.)</SelectItem>
                      <SelectItem value="AT_RISK">Risk Altında / Geçici</SelectItem>
                      <SelectItem value="UNKNOWN">Bilinmiyor / Belirtilmedi</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {context?.last_confirmed_at && (
                  <div className="text-xs text-muted-foreground pt-2">
                    Son onay tarihi: <span className="font-mono text-foreground">{new Date(context.last_confirmed_at).toLocaleDateString('tr-TR')}</span>
                  </div>
                )}
              </CardContent>
              <CardFooter className="flex justify-between gap-2 border-t border-border/40 pt-4">
                <Button variant="outline" onClick={handleConfirmContext} disabled={updatingContext}>
                  <CheckCircle2 className="size-4 mr-1.5" />
                  Profili Onayla
                </Button>
                <Button onClick={handleSaveContext} disabled={updatingContext}>
                  Değişiklikleri Kaydet
                </Button>
              </CardFooter>
            </Card>
          </TabsContent>

          {/* TAB 3: UNASSIGNED RESOURCES */}
          <TabsContent value="unassigned" className="space-y-4">
            <Card className="border-border/60">
              <CardHeader>
                <CardTitle className="text-base">Tahsis Edilmemiş Sermaye (Sermaye Korunumu)</CardTitle>
                <CardDescription>
                  Henüz herhangi bir yatırım mandatine veya hedefe bağlanmamış serbest varlıklarınız ve nakit bakiyeleriniz.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <h4 className="text-sm font-semibold mb-2">Varlıklar (Hisse, Fon vb.)</h4>
                  <div className="border border-border/40 rounded-lg overflow-hidden">
                    <table className="w-full text-xs">
                      <thead className="bg-muted/40 border-b border-border/40 text-muted-foreground">
                        <tr>
                          <th className="py-2 px-3 text-left">Sembol</th>
                          <th className="py-2 px-3 text-left">Varlık</th>
                          <th className="py-2 px-3 text-right">Toplam Adet</th>
                          <th className="py-2 px-3 text-right">Tahsis Edilen</th>
                          <th className="py-2 px-3 text-right">Serbest (Tahsis Edilmemiş)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {unassigned?.assets?.map((a) => (
                          <tr key={a.asset_id} className="border-b border-border/20 last:border-none">
                            <td className="py-2 px-3 font-semibold">{a.symbol}</td>
                            <td className="py-2 px-3 text-muted-foreground">{a.name}</td>
                            <td className="py-2 px-3 text-right font-mono">{a.total_quantity}</td>
                            <td className="py-2 px-3 text-right font-mono text-muted-foreground">{a.assigned_quantity}</td>
                            <td className="py-2 px-3 text-right font-mono font-medium text-emerald-500">{a.unassigned_quantity}</td>
                          </tr>
                        ))}
                        {(!unassigned?.assets || unassigned.assets.length === 0) && (
                          <tr>
                            <td colSpan={5} className="py-4 text-center text-muted-foreground">Kayıtlı varlık bulunamadı.</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div>
                  <h4 className="text-sm font-semibold mb-2">Nakit Hesapları</h4>
                  <div className="border border-border/40 rounded-lg overflow-hidden">
                    <table className="w-full text-xs">
                      <thead className="bg-muted/40 border-b border-border/40 text-muted-foreground">
                        <tr>
                          <th className="py-2 px-3 text-left">Para Birimi</th>
                          <th className="py-2 px-3 text-right">Toplam Bakiye</th>
                          <th className="py-2 px-3 text-right">Tahsis Edilen</th>
                          <th className="py-2 px-3 text-right">Serbest (Tahsis Edilmemiş)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {unassigned?.cash_accounts?.map((c) => (
                          <tr key={c.cash_account_id} className="border-b border-border/20 last:border-none">
                            <td className="py-2 px-3 font-semibold">{c.currency}</td>
                            <td className="py-2 px-3 text-right font-mono">{c.total_balance}</td>
                            <td className="py-2 px-3 text-right font-mono text-muted-foreground">{c.assigned_amount}</td>
                            <td className="py-2 px-3 text-right font-mono font-medium text-emerald-500">{c.unassigned_amount}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* MODAL: ADD GOAL */}
        <Dialog open={showGoalModal} onOpenChange={setShowGoalModal}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Yeni Finansal Hedef Ekle</DialogTitle>
              <DialogDescription>
                Hedefin amacını, hedef tutarını ve vadesini belirleyin.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-2 text-xs">
              <div className="space-y-1">
                <Label htmlFor="goal-name">Hedef Adı</Label>
                <Input
                  id="goal-name"
                  placeholder="Örn: Ev Peşinatı, Emeklilik Fonu"
                  value={newGoalName}
                  onChange={(e) => setNewGoalName(e.target.value)}
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="goal-type">Hedef Türü</Label>
                <Select value={newGoalType} onValueChange={setNewGoalType}>
                  <SelectTrigger id="goal-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="HOME_PURCHASE">Ev Alımı (Home Purchase)</SelectItem>
                    <SelectItem value="RETIREMENT">Emeklilik (Retirement)</SelectItem>
                    <SelectItem value="EMERGENCY_RESERVE">Acil Durum Rezervi (Emergency Reserve)</SelectItem>
                    <SelectItem value="EDUCATION">Eğitim (Education)</SelectItem>
                    <SelectItem value="WEALTH_GROWTH">Varlık Büyütme (Wealth Growth)</SelectItem>
                    <SelectItem value="TRAVEL">Seyahat (Travel)</SelectItem>
                    <SelectItem value="OTHER">Diğer</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label htmlFor="goal-amount">Hedef Tutar (TRY)</Label>
                <Input
                  id="goal-amount"
                  type="number"
                  placeholder="Örn: 500000"
                  value={newGoalAmount}
                  onChange={(e) => setNewGoalAmount(e.target.value)}
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="goal-date">Hedef Tarih</Label>
                <Input
                  id="goal-date"
                  type="date"
                  value={newGoalDate}
                  onChange={(e) => setNewGoalDate(e.target.value)}
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="goal-prio">Öncelik</Label>
                <Select value={newGoalPriority} onValueChange={setNewGoalPriority}>
                  <SelectTrigger id="goal-prio">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ESSENTIAL">Zorunlu / Vazgeçilemez (Essential)</SelectItem>
                    <SelectItem value="IMPORTANT">Önemli (Important)</SelectItem>
                    <SelectItem value="ASPIRATIONAL">İsteğe Bağlı (Aspirational)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowGoalModal(false)}>İptal</Button>
              <Button onClick={handleCreateGoal}>Oluştur</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* MODAL: ADD MANDATE */}
        <Dialog open={showMandateModal} onOpenChange={setShowMandateModal}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Yeni Yatırım Mandati Oluştur</DialogTitle>
              <DialogDescription>
                Belirli bir hedefe veya bağımsız amaca hizmet eden kapsamlı sermaye havuzu (sleeve).
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-2 text-xs">
              <div className="space-y-1">
                <Label htmlFor="mandate-name">Mandat Adı</Label>
                <Input
                  id="mandate-name"
                  placeholder="Örn: Ev Koruma Havuzu, Büyüme Portföyü"
                  value={newMandateName}
                  onChange={(e) => setNewMandateName(e.target.value)}
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="mandate-type">Mandat Türü</Label>
                <Select value={newMandateType} onValueChange={setNewMandateType}>
                  <SelectTrigger id="mandate-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="PRESERVATION">Sermaye Koruma (Preservation)</SelectItem>
                    <SelectItem value="GROWTH">Büyüme (Growth)</SelectItem>
                    <SelectItem value="INCOME">Gelir Odaklı (Income)</SelectItem>
                    <SelectItem value="RESERVE">Rezerv (Reserve)</SelectItem>
                    <SelectItem value="SPECULATIVE">Spekülatif (Speculative)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label htmlFor="mandate-goal">Bağlı Hedef (Opsiyonel)</Label>
                <Select value={newMandateGoalId} onValueChange={setNewMandateGoalId}>
                  <SelectTrigger id="mandate-goal">
                    <SelectValue placeholder="Hedef Seçin" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Bağımsız (Hedefsiz)</SelectItem>
                    {goals.map((g) => (
                      <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label htmlFor="mandate-risk">Risk Kapasitesi</Label>
                <Select value={newMandateRisk} onValueChange={setNewMandateRisk}>
                  <SelectTrigger id="mandate-risk">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="LOW">Düşük (Low)</SelectItem>
                    <SelectItem value="MODERATE">Orta (Moderate)</SelectItem>
                    <SelectItem value="HIGH">Yüksek (High)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowMandateModal(false)}>İptal</Button>
              <Button onClick={handleCreateMandate}>Oluştur</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* MODAL: VIRTUAL TRANSFER */}
        <Dialog open={showTransferModal} onOpenChange={setShowTransferModal}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Mandatler Arası Sanal Sermaye Transferi</DialogTitle>
              <DialogDescription>
                Bu işlem yalnızca sermaye tahsisini (earmark) değiştirir. Gerçek bir alım/satım işlemi yapılmaz, maliyet esası ve toplam net değer değişmez.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-2 text-xs">
              <div className="space-y-1">
                <Label>Kaynak Mandat</Label>
                <Select value={fromMandateId} onValueChange={setFromMandateId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Kaynak mandat seçin" />
                  </SelectTrigger>
                  <SelectContent>
                    {mandates.map((m) => (
                      <SelectItem key={m.id} value={m.id}>{m.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label>Hedef Mandat</Label>
                <Select value={toMandateId} onValueChange={setToMandateId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Hedef mandat seçin" />
                  </SelectTrigger>
                  <SelectContent>
                    {mandates.map((m) => (
                      <SelectItem key={m.id} value={m.id}>{m.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label>Transfer Türü</Label>
                <Select
                  value={transferResourceType}
                  onValueChange={(v) => setTransferResourceType(v as any)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ASSET">Hisse / Varlık Adedi</SelectItem>
                    <SelectItem value="CASH_ACCOUNT">Nakit Tutar (TRY)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {transferResourceType === 'ASSET' ? (
                <>
                  <div className="space-y-1">
                    <Label>Transfer Edilecek Varlık</Label>
                    <Select value={transferAssetId} onValueChange={setTransferAssetId}>
                      <SelectTrigger>
                        <SelectValue placeholder="Varlık seçin" />
                      </SelectTrigger>
                      <SelectContent>
                        {unassigned?.assets?.map((a) => (
                          <SelectItem key={a.asset_id} value={a.asset_id}>{a.symbol} - {a.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <Label>Transfer Edilecek Adet</Label>
                    <Input
                      type="number"
                      placeholder="Örn: 25"
                      value={transferQuantity}
                      onChange={(e) => setTransferQuantity(e.target.value)}
                    />
                  </div>
                </>
              ) : (
                <div className="space-y-1">
                  <Label>Transfer Edilecek Tutar (TRY)</Label>
                  <Input
                    type="number"
                    placeholder="Örn: 10000"
                    value={transferAmount}
                    onChange={(e) => setTransferAmount(e.target.value)}
                  />
                </div>
              )}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowTransferModal(false)}>İptal</Button>
              <Button onClick={handleTransferCapital}>Transferi Gerçekleştir</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}
