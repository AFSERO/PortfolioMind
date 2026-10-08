import Sidebar from './Sidebar'
import TopBar from './TopBar'

interface AppShellProps {
  children: React.ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-background md:flex">
      <a
        href="#main-content"
        className="sr-only z-[100] rounded-md bg-primary px-4 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to content
      </a>
      <Sidebar />
      <div className="min-w-0 flex-1 flex flex-col md:h-screen md:overflow-hidden">
        <TopBar />
        <main
          id="main-content"
          className="min-w-0 flex-1 pt-16 md:overflow-y-auto md:pt-0"
        >
          {children}
        </main>
      </div>
    </div>
  )
}
