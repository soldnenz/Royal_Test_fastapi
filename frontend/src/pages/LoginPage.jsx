import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { useLanguage } from '../contexts/LanguageContext';
import { translations } from '../translations/translations';

const LoginPage = () => {
  const { theme, toggleTheme } = useTheme();
  const { language, changeLanguage } = useLanguage();
  const t = translations[language];

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [loading, setLoading] = useState(false);

  const validate = () => {
    const newErrors = {};
    const isIIN = /^\d{12}$/.test(username);
    const isEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(username);
    if (!username || (!isIIN && !isEmail)) {
      newErrors.username = t.usernameInvalid;
    }
    if (!password) {
      newErrors.password = t.passwordRequired;
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');
    if (!validate()) return;
    setLoading(true);
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, password }),
        credentials: 'include'
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail?.message || 'Error');
      }
      // Redirect on success
      window.location.href = '/';
    } catch (err) {
      setServerError(err.message || 'Error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
      <main className="flex-grow flex items-center justify-center py-12">
        <div className="w-full max-w-md bg-white dark:bg-dark-800 rounded-xl shadow-md p-8">
          <h2 className="text-2xl font-bold mb-6 text-gray-900 dark:text-white">{t.login}</h2>
          {serverError && <div className="text-red-600 mb-4">{serverError}</div>}
          <form onSubmit={handleSubmit} noValidate>
            <div className="mb-4">
              <label className="block text-gray-700 dark:text-gray-300 mb-1">{t.iinOrEmail}</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                  errors.username ? 'border-red-500' : 'border-gray-300 dark:border-gray-700'
                }`}
              />
              {errors.username && <p className="text-red-500 mt-1">{errors.username}</p>}
            </div>
            <div className="mb-4">
              <label className="block text-gray-700 dark:text-gray-300 mb-1">{t.password}</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                  errors.password ? 'border-red-500' : 'border-gray-300 dark:border-gray-700'
                }`}
              />
              {errors.password && <p className="text-red-500 mt-1">{errors.password}</p>}
            </div>
            <div className="flex justify-between items-center mb-6">
              <Link to="/forgot-password" className="text-sm text-primary-600 dark:text-primary-400 hover:underline">
                {t.forgotPassword}
              </Link>
              <Link to="/registration" className="text-sm text-primary-600 dark:text-primary-400 hover:underline">
                {t.signUp}
              </Link>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full btn btn-primary flex justify-center items-center"
            >
              {loading && (
                <svg
                  className="animate-spin h-5 w-5 mr-2 text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v8z"
                  ></path>
                </svg>
              )}
              {t.loginButton}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
};

export default LoginPage; 