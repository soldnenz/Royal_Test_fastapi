// src/App.jsx
import React, { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { LanguageProvider } from './contexts/LanguageContext';
import { ToastContainer } from 'react-toastify';
import { initTheme } from './utils/themeUtil';
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
              
              {/* Test route */}
              <Route path="test/:lobbyId" element={<TestPage />} />

              <Route path="/" element={<MainLayout />}>
                <Route index element={<HomePage />} />
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>

          <ToastContainer
            position="top-right"
            autoClose={5000}
            hideProgressBar={false}
            newestOnTop
            closeOnClick
            rtl={false}
            pauseOnFocusLoss
            draggable
            pauseOnHover
          />
        </Router>
      </LanguageProvider>
    </ThemeProvider>
  );
}

export default App;
