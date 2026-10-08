import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Toaster } from '@/components/ui/sonner'
import ProtectedRoute from '@/components/ProtectedRoute'
import AuthInitializer from '@/components/AuthInitializer'

import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import DashboardPage from '@/pages/DashboardPage'
import AssetsPage from '@/pages/AssetsPage'
import AssetDetailPage from '@/pages/AssetDetailPage'
import SettingsPage from '@/pages/SettingsPage'
import CashPage from '@/pages/CashPage'
import LiabilitiesPage from '@/pages/LiabilitiesPage'
import LiabilityStatementsPage from '@/pages/LiabilityStatementsPage'
import StatementDetailPage from '@/pages/StatementDetailPage'
import StatementImportPage from '@/pages/StatementImportPage'

import AllocationPage from '@/pages/AllocationPage'
import WatchlistPage from '@/pages/WatchlistPage'
import ResearchPage from '@/pages/ResearchPage'
import MonitoringPage from '@/pages/MonitoringPage'
import BriefingPage from '@/pages/BriefingPage'
import DecisionsPage from '@/pages/DecisionsPage'
import CopilotPage from '@/pages/CopilotPage'
import OnboardingPage from '@/pages/OnboardingPage'
import InvestorProfilePage from '@/pages/InvestorProfilePage'
import FinancialProfilePage from '@/pages/FinancialProfilePage'

function App() {
  return (
    <BrowserRouter>
      {/* Restores session from refresh-token cookie on every app load */}
      <AuthInitializer />

      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected routes */}
        <Route
          path="/onboarding"
          element={
            <ProtectedRoute>
              <OnboardingPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/assets"
          element={
            <ProtectedRoute>
              <AssetsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/holdings"
          element={<Navigate to="/assets" replace />}
        />
        <Route
          path="/assets/:id"
          element={
            <ProtectedRoute>
              <AssetDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/allocation"
          element={
            <ProtectedRoute>
              <AllocationPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/watchlist"
          element={
            <ProtectedRoute>
              <WatchlistPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/research"
          element={
            <ProtectedRoute>
              <ResearchPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/monitoring"
          element={
            <ProtectedRoute>
              <MonitoringPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/copilot"
          element={
            <ProtectedRoute>
              <CopilotPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/briefing"
          element={
            <ProtectedRoute>
              <BriefingPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/decisions"
          element={
            <ProtectedRoute>
              <DecisionsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/journal"
          element={<Navigate to="/decisions" replace />}
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings/investor-profile"
          element={
            <ProtectedRoute>
              <InvestorProfilePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings/financial-profile"
          element={
            <ProtectedRoute>
              <FinancialProfilePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/goals"
          element={
            <ProtectedRoute>
              <FinancialProfilePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/cash"
          element={
            <ProtectedRoute>
              <CashPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/liabilities"
          element={
            <ProtectedRoute>
              <LiabilitiesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/liabilities/:liabilityId/statements"
          element={
            <ProtectedRoute>
              <LiabilityStatementsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/liabilities/:liabilityId/statements/import"
          element={
            <ProtectedRoute>
              <StatementImportPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/liabilities/:liabilityId/statements/:statementId"
          element={
            <ProtectedRoute>
              <StatementDetailPage />
            </ProtectedRoute>
          }
        />

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>

      <Toaster position="top-right" richColors closeButton />
    </BrowserRouter>
  )
}

export default App
