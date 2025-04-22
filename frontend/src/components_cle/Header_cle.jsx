import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { useLanguage } from '../contexts/LanguageContext';
import { translations } from '../translations/translations';

const Header_cle = () => {
  const { theme, toggleTheme } = useTheme();
  const { language, changeLanguage } = useLanguage();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  
  const t = translations[language];

  const toggleMenu = () => {
    setIsMenuOpen(!isMenuOpen);
  };

  return (
    <header className="bg-white/95 dark:bg-dark-800/95 backdrop-blur-md border-b border-gray-200 dark:border-gray-700 shadow-sm sticky top-0 z-50 transition-all duration-300">
      <div className="container-custom mx-auto px-4 flex items-center justify-between py-4">
        {/* Logo */}
        <Link to="/" className="flex items-center space-x-2">
          <span className="text-2xl font-bold">
            <span className="bg-gradient-to-r from-primary-500 to-primary-600 bg-clip-text text-transparent drop-shadow-sm">Royal</span>
            <span className="text-gray-900 dark:text-white">Test</span>
          </span>
        </Link>

        {/* Mobile Menu Button */}
        <div className="lg:hidden flex items-center space-x-2">
          {/* Theme Toggle Mobile */}
          <button 
            onClick={toggleTheme} 
            className="p-2 rounded-full bg-gray-100 dark:bg-dark-700 hover:bg-gray-200 dark:hover:bg-dark-600 transition-colors shadow-sm"
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>
          
          <button 
            onClick={toggleMenu}
            className="flex items-center p-2 rounded-md text-gray-900 dark:text-white"
            aria-label="Toggle menu"
          >
            {isMenuOpen ? (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>

        {/* Desktop Navigation */}
        <nav className="hidden lg:flex items-center space-x-6">

          {/* Language Selector */}
          <div className="relative group">
            <button 
              className="flex items-center space-x-1 text-gray-900 dark:text-white hover:text-primary-500 dark:hover:text-primary-400 transition-colors"
            >
              <span>{language === 'ru' ? 'РУС' : language === 'kz' ? 'ҚАЗ' : 'ENG'}</span>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            
            <div className="absolute right-0 mt-2 py-2 w-24 bg-white dark:bg-dark-800 rounded-md shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 border border-gray-200 dark:border-gray-700">
              <button 
                onClick={() => changeLanguage('ru')}
                className={`block px-4 py-2 text-sm w-full text-left ${language === 'ru' ? 'text-primary-500' : 'text-gray-900 dark:text-white'} hover:bg-gray-100 dark:hover:bg-dark-700`}
              >
                {t.russian}
              </button>
              <button 
                onClick={() => changeLanguage('kz')}
                className={`block px-4 py-2 text-sm w-full text-left ${language === 'kz' ? 'text-primary-500' : 'text-gray-900 dark:text-white'} hover:bg-gray-100 dark:hover:bg-dark-700`}
              >
                {t.kazakh}
              </button>
              <button 
                onClick={() => changeLanguage('en')}
                className={`block px-4 py-2 text-sm w-full text-left ${language === 'en' ? 'text-primary-500' : 'text-gray-900 dark:text-white'} hover:bg-gray-100 dark:hover:bg-dark-700`}
              >
                {t.english}
              </button>
            </div>
          </div>
          
          {/* Theme Toggle */}
          <button 
            onClick={toggleTheme} 
            className="p-2 rounded-full bg-gray-100 dark:bg-dark-700 hover:bg-gray-200 dark:hover:bg-dark-600 transition-colors shadow-md"
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>
        </nav>
      </div>

      {/* Mobile Menu */}
      {isMenuOpen && (
        <div className="lg:hidden bg-white/95 dark:bg-dark-800/95 backdrop-blur-md border-t border-gray-200 dark:border-gray-700 shadow-lg">
          <div className="container-custom py-4 flex flex-col space-y-4">
            {/* Login/Register Buttons */}
            <div className="flex flex-col space-y-2">
              <Link 
                to="/login" 
                className="py-2 text-gray-900 dark:text-white hover:text-primary-600 transition-colors"
                onClick={() => setIsMenuOpen(false)}
              >
                {t.login}
              </Link>
              <Link 
                to="/registration" 
                className="py-2 px-4 bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-600 hover:to-primary-700 text-white rounded-lg text-center shadow-md"
                onClick={() => setIsMenuOpen(false)}
              >
                {t.register}
              </Link>
            </div>
            
            {/* Language Options */}
            <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{t.selectLanguage}:</p>
              <div className="flex space-x-4">
                <button 
                  onClick={() => changeLanguage('ru')}
                  className={`px-3 py-1 rounded-md ${language === 'ru' ? 'bg-primary-500 text-white shadow-md' : 'bg-gray-100 dark:bg-dark-700 text-gray-900 dark:text-white'}`}
                >
                  РУС
                </button>
                <button 
                  onClick={() => changeLanguage('kz')}
                  className={`px-3 py-1 rounded-md ${language === 'kz' ? 'bg-primary-500 text-white shadow-md' : 'bg-gray-100 dark:bg-dark-700 text-gray-900 dark:text-white'}`}
                >
                  ҚАЗ
                </button>
                <button 
                  onClick={() => changeLanguage('en')}
                  className={`px-3 py-1 rounded-md ${language === 'en' ? 'bg-primary-500 text-white shadow-md' : 'bg-gray-100 dark:bg-dark-700 text-gray-900 dark:text-white'}`}
                >
                  ENG
                </button>
              </div>
            </div>
            
            <div className="flex items-center border-t border-gray-200 dark:border-gray-700 pt-4">
              <button 
                onClick={toggleTheme} 
                className="p-2 rounded-full bg-gray-100 dark:bg-dark-700 hover:bg-gray-200 dark:hover:bg-dark-600 transition-colors shadow-sm"
                aria-label="Toggle theme"
              >
                {theme === 'dark' ? (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                  </svg>
                )}
              </button>
              <span className="ml-2 text-gray-900 dark:text-white">
                {theme === 'dark' ? t.lightTheme : t.darkTheme}
              </span>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

export default Header_cle; 