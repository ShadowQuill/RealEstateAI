import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import Navbar from "@/components/Navbar";
import ErrorBoundary from "@/components/ErrorBoundary";
import DashboardPage from "@/sections/DashboardPage";
import CityListingsPage from "@/sections/CityListingsPage";
import ListingDetailPage from "@/sections/ListingDetailPage";
import NLPAnalysisPage from "@/sections/NLPAnalysisPage";
import PricePredictPage from "@/sections/PricePredictPage";
import "./App.css";

function AppRoutes() {
  const location = useLocation();
  // 每个路由用独立 ErrorBoundary 包裹，并加 key 强制重建，
  // 避免某页卸载/渲染时的 DOM 协调错误污染整个导航。
  return (
    <Routes>
      <Route path="/" element={<ErrorBoundary key="dashboard"><DashboardPage /></ErrorBoundary>} />
      <Route path="/listings" element={<ErrorBoundary key="listings"><CityListingsPage /></ErrorBoundary>} />
      <Route path="/predict/:id" element={<ErrorBoundary key={location.pathname}><ListingDetailPage /></ErrorBoundary>} />
      <Route path="/predict" element={<ErrorBoundary key="predict"><PricePredictPage /></ErrorBoundary>} />
      <Route path="/nlp" element={<ErrorBoundary key="nlp"><NLPAnalysisPage /></ErrorBoundary>} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background">
        <Navbar />
        <main>
          <AppRoutes />
        </main>
        <Toaster richColors />
      </div>
    </BrowserRouter>
  );
}

export default App;
