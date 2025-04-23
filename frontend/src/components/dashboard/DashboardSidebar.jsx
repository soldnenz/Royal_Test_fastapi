import { Link, useLocation } from 'react-router-dom';
import { useLanguage } from '../../contexts/LanguageContext';
import { translations } from '../../translations/translations';
import { useTranslation } from 'react-i18next';
import { useMediaQuery } from 'react-responsive';
import React from 'react';

const DashboardSidebar = ({ isOpen, toggleSidebar }) => {
  const { language } = useLanguage();
  const t = translations[language];
  const location = useLocation();
  const { t: i18nT } = useTranslation();
  const isMobile = useMediaQuery({ maxWidth: 768 });

  // Navigation items - can be expanded later
  const navItems = [
    {
      name: t.tests,
      path: '/dashboard/tests',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
      )
    },
    {
      name: t.statistics,
      path: '/dashboard/statistics',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      )
    },
    {
      name: t.referralSystem,
      path: '/dashboard/referrals',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
      )
    },
    {
      name: t.subscription,
      path: '/dashboard/subscription',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
        </svg>
      )
    }
  ];

  return (
    <aside 
      className={`fixed left-0 top-0 z-40 h-screen overflow-hidden transition-all duration-300 
                  bg-white border-r border-gray-200 dark:bg-gray-800 dark:border-gray-700
                  ${isOpen ? 'w-64' : isMobile ? 'w-0' : 'w-16'}`}
    >
      <div className="h-full flex flex-col">
        {/* Sidebar header */}
        <div className={`flex items-center px-4 py-3 ${isOpen ? 'justify-between' : 'justify-center'} 
                        border-b border-gray-200 dark:border-gray-700`}>
          {isOpen ? (
            <>
              <Link to="/" className="flex items-center">
                <img src="/logo.png" alt="Royal Test Logo" className="h-8" />
                <span className="ml-2 text-xl font-bold text-gray-800 dark:text-white">Royal Test</span>
              </Link>
              <button 
                onClick={toggleSidebar} 
                className="p-1 rounded-full text-gray-500 hover:text-gray-900 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-white dark:hover:bg-gray-700"
              >
                <span className="sr-only">{i18nT.closeSidebar}</span>
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
            </>
          ) : (
            <button 
              onClick={toggleSidebar} 
              className="p-1 rounded-full text-gray-500 hover:text-gray-900 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-white dark:hover:bg-gray-700 w-full flex justify-center"
            >
              <span className="sr-only">{i18nT.openSidebar}</span>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          )}
        </div>

        {/* Sidebar content */}
        <div className="flex-1 px-2 py-4 overflow-y-auto">
          <ul className="space-y-2">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              const linkClasses = `flex ${isOpen ? 'items-center justify-start px-4' : 'flex-col items-center justify-center px-2'} 
                py-2.5 text-base font-normal rounded-lg transition-all duration-200 group
                ${isActive 
                  ? 'bg-primary-50 text-primary-600 dark:bg-primary-900/20 dark:text-primary-500' 
                  : 'text-gray-900 hover:bg-gray-100 dark:text-white dark:hover:bg-gray-700'
                }`;

              return (
                <li key={item.path}>
                  <Link to={item.path} className={linkClasses}>
                    {/* Icon with style adjustments based on sidebar state */}
                    <div className={`flex items-center justify-center ${isOpen ? 'mr-2' : 'mb-1'}`}>
                      {React.cloneElement(item.icon, { 
                        className: `h-6 w-6 ${isActive ? 'text-primary-600 dark:text-primary-500' : ''}`
                      })}
                    </div>
                    
                    {/* Text - only show if sidebar is open */}
                    {isOpen && <span>{item.name}</span>}

                    {/* Show smaller text under icon when sidebar is collapsed */}
                    {!isOpen && (
                      <span className="text-xs text-center mt-0.5 max-w-10 truncate">
                        {item.name}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </aside>
  );
};

export default DashboardSidebar; 