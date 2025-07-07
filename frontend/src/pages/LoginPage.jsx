import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { useLanguage } from '../contexts/LanguageContext';
import { translations } from '../translations/translations';
import TurnstileWidget from '../components/TurnstileWidget';

const LoginPage = () => {
  const { theme, toggleTheme } = useTheme();
  const { language, changeLanguage } = useLanguage();
  const t = translations[language];

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState('');
  const [turnstileError, setTurnstileError] = useState('');

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
    
    // Turnstile validation
    if (!turnstileToken) {
      setTurnstileError('Пожалуйста, завершите проверку безопасности');
      return false;
    }
    
    setErrors(newErrors);
    setTurnstileError('');
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
        body: JSON.stringify({ 
          username, 
          password,
          cf_turnstile_response: turnstileToken
        }),
        credentials: 'include'
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.message || data.details?.message || 'Произошла ошибка при входе');
      }
      // Redirect to dashboard on success
      window.location.href = '/dashboard';
    } catch (err) {
      setServerError(err.message || 'Ошибка сервера');
    } finally {
      setLoading(false);
    }
  };

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  const handleTurnstileSuccess = (token) => {
    setTurnstileToken(token);
    setTurnstileError('');
  };

  const handleTurnstileError = () => {
    setTurnstileToken('');
    setTurnstileError('Ошибка проверки безопасности. Попробуйте еще раз.');
  };

  const handleTurnstileExpired = () => {
    setTurnstileToken('');
    setTurnstileError('Время проверки истекло. Пожалуйста, пройдите проверку снова.');
  };

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
      <main className="flex-grow flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="w-full max-w-md bg-white dark:bg-dark-800 rounded-xl overflow-hidden transform transition-all duration-300 hover:scale-[1.01]"
             style={{ boxShadow: theme === 'light' ? '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)' : '' }}>
          
          <div className="bg-gradient-to-r from-primary-600 to-primary-400 h-3"></div>
          
          <div className="p-8">
            <h2 className="text-3xl font-bold mb-6 text-gray-900 dark:text-white text-center">{t.login}</h2>
            
            {serverError && (
              <div className="text-white bg-red-500 p-3 rounded-lg mb-4 animate-pulse">
                {serverError}
              </div>
            )}
            
            <form onSubmit={handleSubmit} noValidate className="space-y-6">
              <div>
                <label className="block text-gray-700 dark:text-gray-300 mb-2 font-medium">{t.iinOrEmail}</label>
                <div className="relative">
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 
                      bg-white dark:bg-gray-700 text-gray-900 dark:text-white transition-all duration-200
                      ${errors.username ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}`}
                  />
                  <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none text-gray-400">
                    {/* You can add an icon here */}
                  </div>
                </div>
                {errors.username && <p className="text-red-500 mt-1 text-sm">{errors.username}</p>}
              </div>
              
              <div>
                <label className="block text-gray-700 dark:text-gray-300 mb-2 font-medium">{t.password}</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 
                      bg-white dark:bg-gray-700 text-gray-900 dark:text-white pr-10 transition-all duration-200
                      ${errors.password ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}`}
                  />
                  <button 
                    type="button" 
                    className="absolute inset-y-0 right-0 pr-3 flex items-center"
                    onClick={togglePasswordVisibility}
                  >
                    {showPassword ? (
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 text-gray-600 dark:text-gray-400">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
                      </svg>
                    ) : (
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 text-gray-600 dark:text-gray-400">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                      </svg>
                    )}
                  </button>
                </div>
                {errors.password && <p className="text-red-500 mt-1 text-sm">{errors.password}</p>}
              </div>
              
              {/* Turnstile Widget */}
              <div>
                <TurnstileWidget
                  onSuccess={handleTurnstileSuccess}
                  onError={handleTurnstileError}
                  onExpired={handleTurnstileExpired}
                  size="normal"
                  theme="auto"
                />
                {turnstileError && (
                  <p className="text-red-500 mt-1 text-sm">{turnstileError}</p>
                )}
              </div>
              
              <div className="flex flex-col sm:flex-row justify-between items-center gap-3">
                <Link to="/forgot-password" className="text-sm text-primary-600 dark:text-primary-400 hover:underline transition-all">
                  {t.forgotPassword}
                </Link>
                <Link to="/registration" className="text-sm text-primary-600 dark:text-primary-400 hover:underline transition-all">
                  {t.signUp}
                </Link>
              </div>
              
              <button
                type="submit"
                disabled={loading}
                className="w-full btn btn-primary flex justify-center items-center py-3 rounded-lg hover:shadow-lg transition-all duration-300 transform hover:-translate-y-1"
              >
                {loading ? (
                  <div className="flex items-center justify-center">
                    <svg
                      className="animate-spin h-8 w-8 mr-3 text-white"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      ></path>
                    </svg>
                    <span className="text-lg">{t.loading || 'Loading...'}</span>
                  </div>
                ) : (
                  <span className="text-lg font-medium">{t.loginButton}</span>
                )}
              </button>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
};

export default LoginPage; 