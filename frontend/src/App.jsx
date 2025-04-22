import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { LanguageProvider } from './contexts/LanguageContext';
import MainLayout from './layouts/MainLayout';
import CleLayout from './layouts/cleLayout';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
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
            <Route path="/" element={<MainLayout />}>
              <Route index element={<HomePage />} />
              <Route path="registration" element={<div className="container-custom py-12 text-center"><h1 className="text-2xl font-bold">Страница регистрации</h1><p>Страница в разработке</p></div>} />
            </Route>
          </Routes>
        </Router>
      </LanguageProvider>
    </ThemeProvider>
  );
}

export default App;
