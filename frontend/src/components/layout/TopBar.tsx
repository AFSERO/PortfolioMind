import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Bell,
  Check,
  ChevronDown,
  LogOut,
  Search,
  Settings,
  Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuthStore } from '@/store'
import { useDashboardStore, type DashboardCurrency } from '@/store/dashboardStore'

const CURRENCIES: { code: DashboardCurrency; symbol: string; label: string }[] = [
  { code: 'TRY', symbol: '₺', label: 'Turkish Lira' },
  { code: 'USD', symbol: '$', label: 'US Dollar' },
  { code: 'EUR', symbol: '€', label: 'Euro' },
]

export default function TopBar() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const { currency, setCurrency } = useDashboardStore()
  const [searchQuery, setSearchQuery] = useState('')

  const initials = (user?.display_name ?? user?.email ?? 'PM').slice(0, 2).toUpperCase()

  const handleLogout = async () => {
    try {
      await logout()
      navigate('/login')
    } catch {
      toast.error('Logout failed')
    }
  }

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    // Navigate to holdings with search filter or monitoring
    navigate(`/assets?q=${encodeURIComponent(searchQuery.trim())}`)
  }

  return (
    <header className="hidden h-14 shrink-0 items-center justify-between border-b border-border/60 bg-card/40 px-6 backdrop-blur md:flex">
      {/* Search Input */}
      <div className="flex flex-1 items-center max-w-md">
        <form onSubmit={handleSearchSubmit} className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" aria-hidden="true" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search ticker, company, or topic..."
            className="h-9 w-full rounded-lg border border-input/60 bg-background/50 pl-9 pr-14 text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-0.5 pointer-events-none">
            <kbd className="rounded border border-border/80 bg-muted/60 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
              Ctrl K
            </kbd>
          </div>
        </form>
      </div>

      {/* Right Utilities */}
      <div className="flex items-center gap-3">
        {/* Currency Selector */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1.5 border-border/60 bg-background/50 px-2.5 text-xs font-medium text-foreground hover:bg-accent"
              aria-label="Select display currency"
            >
              <span className="font-mono font-semibold text-teal-400">
                {CURRENCIES.find((c) => c.code === currency)?.symbol}
              </span>
              <span>{currency}</span>
              <ChevronDown className="size-3 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40">
            <DropdownMenuLabel className="text-xs text-muted-foreground">
              Display Currency
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {CURRENCIES.map((c) => (
              <DropdownMenuItem
                key={c.code}
                onClick={() => setCurrency(c.code)}
                className="flex items-center justify-between text-xs"
              >
                <span className="flex items-center gap-2">
                  <span className="font-mono text-muted-foreground">{c.symbol}</span>
                  <span>{c.code}</span>
                </span>
                {currency === c.code && <Check className="size-3.5 text-teal-400" />}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Attention / Monitoring Shortcut */}
        <Button
          variant="ghost"
          size="icon"
          className="size-8 text-muted-foreground hover:text-foreground relative"
          onClick={() => navigate('/monitoring')}
          title="Attention & Monitoring"
          aria-label="Attention & Monitoring"
        >
          <Bell className="size-4" />
          <span className="absolute top-1.5 right-1.5 size-1.5 rounded-full bg-teal-400/80" />
        </Button>

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="relative size-8 rounded-full p-0 focus-visible:ring-1 focus-visible:ring-ring"
              aria-label="User account menu"
            >
              <Avatar className="size-8 border border-border/80">
                <AvatarFallback className="bg-teal-500/15 text-xs font-semibold text-teal-300">
                  {initials}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium leading-none text-foreground">
                  {user?.display_name ?? 'Investor'}
                </p>
                <p className="text-xs leading-none text-muted-foreground truncate">
                  {user?.email}
                </p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild className="text-xs">
              <Link to="/settings" className="flex items-center gap-2 cursor-pointer">
                <Settings className="size-4" />
                <span>Settings</span>
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild className="text-xs">
              <Link to="/monitoring" className="flex items-center gap-2 cursor-pointer">
                <Sparkles className="size-4 text-teal-400" />
                <span>Intelligence Status</span>
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={handleLogout}
              className="text-xs text-red-400 focus:text-red-400 focus:bg-red-500/10 cursor-pointer"
            >
              <LogOut className="size-4 mr-2" />
              <span>Log out</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
