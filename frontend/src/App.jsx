import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { LanguageProvider } from './contexts/LanguageContext';
import { ToastContainer } from 'react-toastify';
import MainLayout from './layouts/MainLayout';
import CleLayout from './layouts/cleLayout';
import DashboardLayout from './layouts/DashboardLayout';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import RegistrationPage from './pages/RegistrationPage';
import DashboardHome from './pages/dashboard/DashboardHome';
import SubscriptionPage from './pages/dashboard/SubscriptionPage';
import PaymentPage from './pages/dashboard/PaymentPage';
import ReferralSystemPage from './pages/dashboard/ReferralSystemPage';
import PromoCodesPage from './pages/dashboard/PromoCodesPage';
import './App.css';

function App() {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <Router>
          <Routes>
            <Route path="login" element={<CleLayout />}>
              <Route index element={<LoginPage />} />
            </Route>
            <Route path="registration" element={<CleLayout />}>
              <Route index element={<RegistrationPage />} />
            </Route>
            <Route path="dashboard" element={<DashboardLayout />}>
              <Route index element={<DashboardHome />} />
              <Route path="tests" element={<div className="p-4 bg-white dark:bg-gray-800 rounded-lg"><h1 className="text-xl font-bold mb-2">Тесты</h1><p>Страница тестов находится в разработке</p></div>} />
              <Route path="statistics" element={<div className="p-4 bg-white dark:bg-gray-800 rounded-lg"><h1 className="text-xl font-bold mb-2">Статистика</h1><p>Страница статистики находится в разработке</p></div>} />
              <Route path="referrals" element={<ReferralSystemPage />} />
              <Route path="subscription" element={<SubscriptionPage />} />
              <Route path="payment" element={<PaymentPage />} />
              <Route path="promo-codes" element={<PromoCodesPage />} />
              <Route path="profile" element={<div className="p-4 bg-white dark:bg-gray-800 rounded-lg"><h1 className="text-xl font-bold mb-2">Профиль</h1><p>Страница профиля находится в разработке</p></div>} />
              <Route path="settings" element={<div className="p-4 bg-white dark:bg-gray-800 rounded-lg"><h1 className="text-xl font-bold mb-2">Настройки</h1><p>Страница настроек находится в разработке</p></div>} />
            </Route>
            <Route path="/" element={<MainLayout />}>
              <Route index element={<HomePage />} />
            </Route>
          </Routes>
          <ToastContainer position="top-right" autoClose={5000} hideProgressBar={false} newestOnTop closeOnClick rtl={false} pauseOnFocusLoss draggable pauseOnHover />
        </Router>
      </LanguageProvider>
    </ThemeProvider>
  );
}

export default App;
