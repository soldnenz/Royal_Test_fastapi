import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTheme } from '../../contexts/ThemeContext';
import { useLanguage } from '../../contexts/LanguageContext';
import { translations } from '../../translations/translations';

const DashboardHeader = ({ 
  profileData, 
  toggleSidebar, 
  isSidebarOpen, 
  onToggleTheme, 
  onChangeLanguage,
  currentTheme,
  currentLanguage
}) => {
  // Use props for theme/language if provided, otherwise use context
  const themeContext = useTheme();
  const languageContext = useLanguage();
  
  const theme = currentTheme || themeContext.theme;
  const language = currentLanguage || languageContext.language;
  
  const navigate = useNavigate();
  const t = translations[language] || translations['en']; // Fallback to English
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isLanguageOpen, setIsLanguageOpen] = useState(false);
  const profileRef = useRef(null);
  const languageRef = useRef(null);

  // Handle clicks outside the dropdown
  useEffect(() => {
    function handleClickOutside(event) {
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setIsProfileOpen(false);
      }
      if (languageRef.current && !languageRef.current.contains(event.target)) {
        setIsLanguageOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [profileRef, languageRef]);

  // Handle language change with forced component update
  const handleLanguageChange = (newLang) => {
    if (language !== newLang) {
      // Use prop handler if provided, otherwise use context
      if (onChangeLanguage) {
        onChangeLanguage(newLang);
      } else {
        languageContext.changeLanguage(newLang);
      }
      
      setIsLanguageOpen(false);
      
      // Force a re-render by setting a state or reloading the translations
      // This is just to ensure the UI updates immediately
      setTimeout(() => {
        // This will cause a small delay and then reset the state, 
        // which should trigger a re-render if needed
        setIsLanguageOpen(false);
      }, 50);
    }
  };

  // Handle theme toggle
  const handleToggleTheme = () => {
    // Use prop handler if provided, otherwise use context
    if (onToggleTheme) {
      onToggleTheme();
    } else {
      themeContext.toggleTheme();
    }
  };

  // Handle logout
  const handleLogout = async () => {
    try {
      const response = await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include'
      });

      if (response.ok) {
        // Redirect to home page after successful logout
        navigate('/');
      } else {
        console.error('Logout failed');
      }
    } catch (error) {
      console.error('Error during logout:', error);
    }
  };

  return (
    <header className="z-30 flex items-center justify-between h-16 px-4 md:px-6 bg-white dark:bg-gray-800 shadow-sm">
      {/* Left: Mobile menu toggle */}
      <div className="flex items-center">
        <button
          onClick={toggleSidebar}
          className="p-2 mr-3 rounded-lg text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500 flex items-center"
          aria-label={isSidebarOpen ? t.closeSidebar : t.navigation}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <span className="ml-2 text-sm">{isSidebarOpen ? t.closeSidebar : t.navigation}</span>
        </button>
        
      </div>
      
      {/* Right: User info and settings */}
      <div className="flex items-center space-x-1 sm:space-x-3">
        {/* Theme toggle */}
        <button
          onClick={handleToggleTheme}
          className="p-2 rounded-lg text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
          aria-label={theme === 'dark' ? t.lightTheme : t.darkTheme}
        >
          {theme === 'dark' ? (
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
              />
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
              />
            </svg>
          )}
        </button>
        
        {/* Language Dropdown */}
        <div className="relative" ref={languageRef}>
          <button
            className="p-2 rounded-lg text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
            onClick={() => setIsLanguageOpen(!isLanguageOpen)}
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
            </svg>
          </button>
          
          {isLanguageOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg py-1 z-50 border border-gray-200 dark:border-gray-700">
              <button
                onClick={() => handleLanguageChange('ru')}
                className={`block w-full text-left px-4 py-2 text-sm ${
                  language === 'ru'
                    ? 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-100'
                    : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
                }`}
              >
                {t.russian}
              </button>
              <button
                onClick={() => handleLanguageChange('kz')}
                className={`block w-full text-left px-4 py-2 text-sm ${
                  language === 'kz'
                    ? 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-100'
                    : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
                }`}
              >
                {t.kazakh}
              </button>
              <button
                onClick={() => handleLanguageChange('en')}
                className={`block w-full text-left px-4 py-2 text-sm ${
                  language === 'en'
                    ? 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-100'
                    : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
                }`}
              >
                {t.english}
              </button>
            </div>
          )}
        </div>
        
        {/* Profile Dropdown */}
        <div className="relative" ref={profileRef}>
          <button
            onClick={() => setIsProfileOpen(!isProfileOpen)}
            className="flex items-center space-x-3 focus:outline-none focus:ring-2 focus:ring-primary-500 rounded-lg p-1"
          >
            <div className="flex-shrink-0 h-8 w-8 rounded-full bg-primary-500 flex items-center justify-center text-white">
              {profileData?.full_name ? profileData.full_name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div className="hidden md:block">
              <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {profileData?.full_name}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                {profileData?.role === 'admin' ? t.adminRole : (profileData?.role === 'moder' ? t.moderRole : t.userRole)}
              </div>
            </div>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className={`h-5 w-5 text-gray-400 transition-transform duration-200 ${isProfileOpen ? 'transform rotate-180' : ''}`}
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
          
          {isProfileOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg py-1 z-50 border border-gray-200 dark:border-gray-700">
              <div className="border-b border-gray-200 dark:border-gray-700 px-4 py-2">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {profileData?.full_name}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {profileData?.email}
                </p>
              </div>
              
              <Link
                to="/dashboard/profile"
                className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
                onClick={() => setIsProfileOpen(false)}
              >
                {t.profile}
              </Link>
              
              <Link
                to="/dashboard/settings"
                className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
                onClick={() => setIsProfileOpen(false)}
              >
                {t.settings}
              </Link>
              
              <button
                onClick={handleLogout}
                className="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-gray-100 dark:text-red-400 dark:hover:bg-gray-700"
              >
                {t.logout}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default DashboardHeader; 