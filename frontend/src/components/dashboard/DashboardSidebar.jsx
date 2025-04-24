import { Link, useLocation } from 'react-router-dom';
import { useLanguage } from '../../contexts/LanguageContext';
import { translations } from '../../translations/translations';
import React, { useState, useEffect } from 'react';
import { FaHome, FaChartBar, FaClipboardList, FaUserFriends, FaCrown, FaCreditCard, FaUserAlt, FaCog, FaGift, FaUser, FaUsers, FaMoneyBill } from 'react-icons/fa';

const DashboardSidebar = ({ isOpen, toggleSidebar }) => {
  const { language } = useLanguage();
  const t = translations[language];
  const location = useLocation();
  const [isMobile, setIsMobile] = useState(false);
  
  // Check if screen is mobile on component mount and when window resizes
  useEffect(() => {
    const checkIfMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    
    // Initial check
    checkIfMobile();
    
    // Add event listener for window resize
    window.addEventListener('resize', checkIfMobile);
    
    // Clean up
    return () => window.removeEventListener('resize', checkIfMobile);
  }, []);

  // Navigation items - can be expanded later
  const navItems = [
    { name: translations[language].tests, icon: <FaClipboardList className="mr-3 text-lg" />, path: '/dashboard/tests' },
    { name: translations[language].statistics, icon: <FaChartBar className="mr-3 text-lg" />, path: '/dashboard/statistics' },
    { name: translations[language].referralSystem, icon: <FaUserFriends className="mr-3 text-lg" />, path: '/dashboard/referrals' },
    { name: translations[language].subscription, icon: <FaCrown className="mr-3 text-lg" />, path: '/dashboard/subscription' },
    { name: translations[language].promoCodes, icon: <FaGift className="mr-3 text-lg" />, path: '/dashboard/promo-codes' },
  ];

  return (
    <>
      {/* Overlay when sidebar is open on mobile */}
      {isOpen && isMobile && (
        <div 
          className="fixed inset-0 bg-gray-900 bg-opacity-50 z-30"
          onClick={toggleSidebar}
        ></div>
      )}

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
                <Link to="/dashboard" className="flex items-center">
                  <span className="text-xl font-bold text-gray-800 dark:text-white">Royal Test</span>
                </Link>
                <button 
                  onClick={toggleSidebar} 
                  className="p-1 rounded-full text-gray-500 hover:text-gray-900 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-white dark:hover:bg-gray-700"
                >
                  <span className="sr-only">{t.closeSidebar || "Close sidebar"}</span>
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
                <span className="sr-only">{t.openSidebar || "Open sidebar"}</span>
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
      
      {/* Main content wrapper with padding for sidebar */}
      <div className={`transition-all duration-300 ${isOpen ? 'ml-64' : isMobile ? 'ml-0' : 'ml-16'}`}>
        {/* Your dashboard content goes here */}
      </div>
    </>
  );
};

export default DashboardSidebar; 