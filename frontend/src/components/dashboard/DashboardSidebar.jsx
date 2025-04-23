import { Link, useLocation } from 'react-router-dom';
import { useLanguage } from '../../contexts/LanguageContext';
import { translations } from '../../translations/translations';

const DashboardSidebar = ({ isOpen, toggleSidebar }) => {
  const { language } = useLanguage();
  const t = translations[language];
  const location = useLocation();

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
      className={`z-40 flex flex-col bg-white dark:bg-gray-800 shadow-md transition-all duration-300 ease-in-out ${
        isOpen ? 'w-64' : 'w-0 sm:w-20'
      } fixed inset-y-0 left-0 md:relative`}
    >
      {/* Logo and toggle button */}
      <div className="flex items-center justify-between h-16 px-4 bg-primary-600 text-white">
        <div className="flex items-center">
          {/* Only show logo in desktop or when sidebar is open */}
          {isOpen || window.innerWidth >= 768 ? (
            <Link to="/dashboard" className="flex items-center">
              {isOpen ? (
                <span className="text-xl font-bold truncate">Royal Test</span>
              ) : (
                <span className={`text-xl font-bold ${window.innerWidth < 640 ? 'hidden' : ''}`}>RT</span>
              )}
            </Link>
          ) : null}
        </div>
        <button 
          onClick={toggleSidebar}
          className={`p-1 rounded-full hover:bg-primary-500 focus:outline-none focus:ring-2 focus:ring-white ${isOpen ? 'md:hidden' : ''}`}
        >
          {isOpen ? (
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

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto pt-5 pb-4">
        <ul className="space-y-1 px-2">
          {navItems.map((item) => (
            <li key={item.path}>
              <Link
                to={item.path}
                className={`flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors ${
                  location.pathname === item.path || location.pathname.startsWith(`${item.path}/`)
                    ? 'bg-primary-100 text-primary-700 dark:bg-primary-800 dark:text-primary-100'
                    : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
                }`}
              >
                <span className="min-w-[24px]">{item.icon}</span>
                {isOpen && <span className="ml-3">{item.name}</span>}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      {/* Mobile close button at the bottom */}
      <div className="md:hidden p-4">
        <button
          onClick={toggleSidebar}
          className={`block md:hidden w-full text-left px-4 py-2 text-sm font-medium rounded-lg text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700 ${
            isOpen ? 'flex items-center' : 'hidden'
          }`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
          {t.closeSidebar}
        </button>
      </div>
    </aside>
  );
};

export default DashboardSidebar; 