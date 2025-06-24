// src/App.jsx
import React, { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { LanguageProvider } from './contexts/LanguageContext';
import { initTheme } from './utils/themeUtil';
import NotificationSystem from './components/notifications/NotificationSystem';
import './App.css';

const MainLayout      = lazy(() => import('./layouts/MainLayout'));
const CleLayout       = lazy(() => import('./layouts/cleLayout'));
const DashboardLayout = lazy(() => import('./layouts/DashboardLayout'));

const HomePage           = lazy(() => import('./pages/HomePage'));
const LoginPage          = lazy(() => import('./pages/LoginPage'));
const RegistrationPage   = lazy(() => import('./pages/RegistrationPage'));
const DashboardHome      = lazy(() => import('./pages/dashboard/DashboardHome'));
const SubscriptionPage   = lazy(() => import('./pages/dashboard/SubscriptionPage'));
const PaymentPage        = lazy(() => import('./pages/dashboard/PaymentPage'));
const ReferralSystemPage = lazy(() => import('./pages/dashboard/ReferralSystemPage'));
const PromoCodesPage     = lazy(() => import('./pages/dashboard/PromoCodesPage'));
const ProfilePage        = lazy(() => import('./pages/dashboard/ProfilePage'));
const TestDashboardPage  = lazy(() => import('./pages/dashboard/TestDashboardPage'));
const TestPage           = lazy(() => import('./pages/TestPage'));
const TestResultsPage    = lazy(() => import('./pages/TestResultsPage'));
const CreateLobbyPage    = lazy(() => import('./pages/multiplayer/CreateLobbyPage'));
const LobbyWaitingPage   = lazy(() => import('./pages/multiplayer/LobbyWaitingPage'));
const JoinLobbyPage      = lazy(() => import('./pages/multiplayer/JoinLobbyPage'));
const MultiplayerTestPage = lazy(() => import('./pages/multiplayer/MultiplayerTestPage'));

const Placeholder = ({ title }) => (
  <div className="p-4 bg-white dark:bg-gray-800 rounded-lg">
    <h1 className="text-xl font-bold mb-2">{title}</h1>
    <p>Страница находится в разработке</p>
  </div>
);

function App() {
  useEffect(() => {
    // Initialize theme on app start
    initTheme();
    
    // Set HTML language attribute based on stored language
    const savedLanguage = localStorage.getItem('language') || 'ru';
    document.documentElement.lang = savedLanguage;
    
    // докачиваем фоном только существующие чанки
    const prefetch = () => {
      import('./layouts/MainLayout');
      import('./layouts/DashboardLayout');
      import('./pages/HomePage');
      import('./pages/LoginPage');
      import('./pages/RegistrationPage');
      import('./pages/dashboard/DashboardHome');
      import('./pages/dashboard/SubscriptionPage');
      import('./pages/dashboard/PaymentPage');
      import('./pages/dashboard/ReferralSystemPage');
      import('./pages/dashboard/PromoCodesPage');
      import('./pages/dashboard/TestDashboardPage');
      import('./pages/TestPage');
      import('./pages/TestResultsPage');
      import('./pages/multiplayer/CreateLobbyPage');
      import('./pages/multiplayer/LobbyWaitingPage');
      import('./pages/multiplayer/JoinLobbyPage');
      import('./pages/multiplayer/MultiplayerTestPage');
    };

    if ('requestIdleCallback' in window) {
      requestIdleCallback(prefetch);
    } else {
      setTimeout(prefetch, 3000);
    }
  }, []);

  return (
    <ThemeProvider>
      <LanguageProvider>
        <Router>
          <Suspense fallback={<div className="p-4 text-center">Загрузка...</div>}>
            <Routes>
              <Route path="login" element={<CleLayout />}>
                <Route index element={<LoginPage />} />
              </Route>

              <Route path="registration" element={<CleLayout />}>
                <Route index element={<RegistrationPage />} />
              </Route>

              <Route path="dashboard" element={<DashboardLayout />}>
                <Route index element={<DashboardHome />} />
                <Route path="tests"       element={<TestDashboardPage />} />
                <Route path="statistics"  element={<Placeholder title="Статистика" />} />
                <Route path="referrals"    element={<ReferralSystemPage />} />
                <Route path="subscription" element={<SubscriptionPage />} />
                <Route path="payment"      element={<PaymentPage />} />
                <Route path="promo-codes"  element={<PromoCodesPage />} />
                <Route path="profile"      element={<ProfilePage />} />
                <Route path="settings"     element={<Placeholder title="Настройки" />} />
              </Route>
              
              {/* Test routes */}
              <Route path="test/:lobbyId" element={<TestPage />} />
              <Route path="test-results/:lobbyId" element={<TestResultsPage />} />
              
              {/* Multiplayer routes */}
              <Route path="multiplayer/create" element={<CreateLobbyPage />} />
              <Route path="multiplayer/lobby/:lobbyId" element={<LobbyWaitingPage />} />
              <Route path="multiplayer/join/:lobbyId" element={<JoinLobbyPage />} />
              <Route path="multiplayer/test/:lobbyId" element={<MultiplayerTestPage />} />

              <Route path="/" element={<MainLayout />}>
                <Route index element={<HomePage />} />
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>

          <NotificationSystem />
        </Router>
      </LanguageProvider>
    </ThemeProvider>
  );
}

export default App;
