import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Activity,
  Banknote,
  BookOpen,
  Bot,
  BrainCircuit,
  CreditCard,
  Eye,
  LayoutDashboard,
  LogOut,
  Menu,
  PieChart,
  Search,
  Settings,
  Sparkles,
  Target,
  TrendingUp,
} from 'lucide-react'
import { toast } from 'sonner'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { useAuthStore } from '@/store'
import { cn } from '@/utils/cn'

const NAV_GROUPS = [
  {
    label: 'Overview',
    items: [
      { icon: LayoutDashboard, label: 'Dashboard', href: '/dashboard' },
    ],
  },
  {
    label: 'Portfolio',
    hint: 'What I own',
    items: [
      { icon: TrendingUp, label: 'Holdings', href: '/assets' },
      { icon: PieChart, label: 'Allocation', href: '/allocation' },
      { icon: Banknote, label: 'Cash', href: '/cash' },
      { icon: CreditCard, label: 'Liabilities', href: '/liabilities' },
    ],
  },
  {
    label: 'Intelligence',
    hint: 'Attention & research',
    items: [
      { icon: Bot, label: 'Copilot', href: '/copilot' },
      { icon: Sparkles, label: 'Briefing', href: '/briefing' },
      { icon: Eye, label: 'Watchlist', href: '/watchlist' },
      { icon: Search, label: 'Research', href: '/research' },
      { icon: Activity, label: 'Monitoring', href: '/monitoring' },
    ],
  },
  {
    label: 'Planning',
    hint: 'Goals & Profile',
    items: [
      { icon: Target, label: 'Goals & Mandates', href: '/goals' },
    ],
  },
  {
    label: 'Decisions',
    hint: 'Why I acted',
    items: [
      { icon: BookOpen, label: 'Decision Log', href: '/decisions' },
    ],
  },
]

function Brand() {
  return (
    <Link to="/dashboard" className="flex items-center gap-3 rounded-lg focus-visible:ring-offset-card group">
      <span className="flex size-9 items-center justify-center rounded-lg bg-teal-500/15 border border-teal-500/30 text-teal-400 group-hover:bg-teal-500/25 transition-colors">
        <BrainCircuit className="size-5" aria-hidden="true" />
      </span>
      <span>
        <span className="block text-sm font-semibold tracking-tight text-slate-100">PortfolioMind</span>
        <span className="mt-0.5 block text-[10px] font-medium uppercase tracking-wider text-teal-400/80">Investment Intelligence</span>
      </span>
    </Link>
  )
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const initials = (user?.display_name ?? user?.email ?? 'PM').slice(0, 2).toUpperCase()

  const handleLogout = async () => {
    try {
      await logout()
      onNavigate?.()
    } catch {
      toast.error('Logout failed')
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="px-5 py-5 border-b border-border/40">
        <Brand />
      </div>
      <nav aria-label="Primary navigation" className="flex-1 px-3 py-3 overflow-y-auto space-y-5">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="space-y-1">
            <div className="flex items-center justify-between px-3 mb-1.5">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/70">
                {group.label}
              </p>
              {group.hint && (
                <span className="text-[9px] font-medium text-muted-foreground/40 hidden xl:inline">
                  {group.hint}
                </span>
              )}
            </div>
            <div className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const active = location.pathname === item.href || (
                  item.href !== '/dashboard' && location.pathname.startsWith(`${item.href}/`)
                )
                return (
                  <Link
                    key={item.href}
                    to={item.href}
                    onClick={onNavigate}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      'flex min-h-9 items-center gap-2.5 rounded-lg px-3 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
                      active && 'bg-teal-500/12 text-teal-300 font-semibold',
                    )}
                  >
                    <item.icon className={cn('size-4', active ? 'text-teal-400' : 'text-muted-foreground')} aria-hidden="true" />
                    <span>{item.label}</span>
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </nav>
      <div className="border-t border-border/50 p-3">
        <Link
          to="/settings"
          onClick={onNavigate}
          className={cn(
            'flex min-h-9 items-center gap-2.5 rounded-lg px-3 text-xs font-medium text-muted-foreground hover:bg-accent hover:text-foreground',
            location.pathname === '/settings' && 'bg-teal-500/12 text-teal-300 font-semibold',
          )}
        >
          <Settings className="size-4" aria-hidden="true" />
          <span>Settings</span>
        </Link>
        <div className="mt-2.5 flex items-center gap-2.5 rounded-lg bg-muted/40 border border-border/40 p-2">
          <Avatar className="size-8">
            <AvatarFallback className="bg-teal-500/15 text-[11px] font-semibold text-teal-300">
              {initials}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium text-foreground">{user?.display_name ?? 'Account'}</p>
            <p className="truncate text-[11px] text-muted-foreground">{user?.email}</p>
          </div>
          <Button variant="ghost" size="icon" className="size-7 text-muted-foreground hover:text-foreground" onClick={handleLogout} aria-label="Log out">
            <LogOut className="size-3.5" aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function Sidebar() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-40 flex h-16 items-center justify-between border-b bg-background/95 px-4 backdrop-blur md:hidden">
        <Brand />
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" size="icon" aria-label="Open navigation">
              <Menu aria-hidden="true" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[min(88vw,18rem)] p-0">
            <SheetHeader className="sr-only">
              <SheetTitle>Navigation</SheetTitle>
              <SheetDescription>Navigate the NetWorth application.</SheetDescription>
            </SheetHeader>
            <SidebarContent onNavigate={() => setOpen(false)} />
          </SheetContent>
        </Sheet>
      </header>
      <aside className="hidden h-screen w-60 shrink-0 border-r bg-card md:sticky md:top-0 md:flex md:flex-col">
        <SidebarContent />
      </aside>
    </>
  )
}
