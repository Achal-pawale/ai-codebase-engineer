import { Navigate, Route, Routes } from "react-router-dom";
import { RepositoryProvider, useRepository } from "@/state/RepositoryContext";
import { RequireRepository } from "@/components/RequireRepository";
import { AppShell } from "@/components/layout/AppShell";
import { ConnectRepositoryPage } from "@/pages/ConnectRepositoryPage";
import { OverviewPage } from "@/pages/OverviewPage";
import { AskCodebasePage } from "@/pages/AskCodebasePage";
import { InvestigatePage } from "@/pages/InvestigatePage";
import { PlanChangesPage } from "@/pages/PlanChangesPage";
import { ProposedChangesPage } from "@/pages/ProposedChangesPage";
import { TestsPage } from "@/pages/TestsPage";

function RootRoute() {
  const { isReady } = useRepository();
  return isReady ? <Navigate to="/overview" replace /> : <ConnectRepositoryPage />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RootRoute />} />

      <Route element={<RequireRepository />}>
        <Route element={<AppShell />}>
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/ask" element={<AskCodebasePage />} />
          <Route path="/investigate" element={<InvestigatePage />} />
          <Route path="/plan" element={<PlanChangesPage />} />
          <Route path="/changes" element={<ProposedChangesPage />} />
          <Route path="/tests" element={<TestsPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <RepositoryProvider>
      <AppRoutes />
    </RepositoryProvider>
  );
}
