import React, { useState, useEffect, useCallback } from 'react';
import { Link, useLocation, NavLink } from 'react-router-dom';
import './DashboardSidebar.css';

// Multilingual menu sections
const menuSections = [
  {
    title: {
      ru: 'Основное',
      kz: 'Негізгі',
      en: 'Main'
    },
    items: [
      { 
        to: '/dashboard', 
        icon: 'bx bxs-dashboard', 
        text: {
          ru: 'Дашборд',
          kz: 'Басқару тақтасы',
          en: 'Dashboard'
        }
      }
    ]
  },
  {
    title: {
      ru: 'Управление',
      kz: 'Басқару',
      en: 'Management'
    },
    items: [
      { 
        to: '/users', 
        icon: 'bx bx-user', 
        text: {
          ru: 'Пользователи',
          kz: 'Пайдаланушылар',
          en: 'Users'
        }
      },
      { 
        to: '/tests', 
        icon: 'bx bx-test-tube', 
        text: {
          ru: 'Тесты',
          kz: 'Тесттер',
          en: 'Tests'
        }
      },
      { 
        to: '/subscriptions', 
        icon: 'bx bx-credit-card', 
        text: {
          ru: 'Подписки',
          kz: 'Жазылымдар',
          en: 'Subscriptions'
        }
      },
      { 
        to: '/referrals', 
        icon: 'bx bx-link-alt', 
        text: {
          ru: 'Рефералы',
          kz: 'Реферралдар',
          en: 'Referrals'
        }
      },
      { 
        to: '/transactions', 
        icon: 'bx bx-transfer', 
        text: {
          ru: 'Транзакции',
          kz: 'Транзакциялар',
          en: 'Transactions'
        }
      }
    ]
  },
  {
    title: {
      ru: 'Настройки',
      kz: 'Параметрлер',
      en: 'Settings'
    },
    items: [
      { 
        to: '/admin', 
        icon: 'bx bx-cog', 
        text: {
          ru: 'Администрирование',
          kz: 'Әкімшілік',
          en: 'Administration'
        }
      }
    ]
  }
];

const DashboardSidebar = ({ isOpen, toggleSidebar, className = '' }) => {
  const location = useLocation();
  const [expandedSection, setExpandedSection] = useState(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 1024);
  const [isCompact, setIsCompact] = useState(window.innerWidth <= 1200 && window.innerWidth > 1024);
  const [touchStartX, setTouchStartX] = useState(null);
  const [displayLanguage, setDisplayLanguage] = useState(localStorage.getItem('displayLanguage') || 'ru');
  
  // Helper function to get text in the current language
  const getText = (textObj) => {
    if (!textObj) return '';
    
    if (typeof textObj === 'string') {
      return textObj;
    }
    
    return textObj[displayLanguage] || textObj.ru || '';
  };
  
  // Handle language change
  const changeLanguage = (language) => {
    setDisplayLanguage(language);
    localStorage.setItem('displayLanguage', language);
  };

  // Обработка событий свайпа
  const handleTouchStart = (e) => {
    setTouchStartX(e.touches[0].clientX);
  };
  
  const handleTouchEnd = (e) => {
    if (!touchStartX) return;
    
    const touchEndX = e.changedTouches[0].clientX;
    const deltaX = touchEndX - touchStartX;
    
    // Если свайп вправо при закрытом сайдбаре - открыть его
    if (deltaX > 100 && !isOpen) {
      toggleSidebar();
    }
    
    // Если свайп влево при открытом сайдбаре - закрыть его
    if (deltaX < -100 && isOpen) {
      toggleSidebar();
    }
    
    setTouchStartX(null);
  };
  
  useEffect(() => {
    const handleResize = () => {
      const mobileView = window.innerWidth <= 1024;
      const compactView = window.innerWidth <= 1200 && window.innerWidth > 1024;
      
      setIsMobile(mobileView);
      setIsCompact(compactView);
    };
    
    handleResize(); // Вызов при монтировании
    window.addEventListener('resize', handleResize);
    
    // Добавляем обработчики событий для мобильного свайпа
    document.addEventListener('touchstart', handleTouchStart);
    document.addEventListener('touchend', handleTouchEnd);
    
    return () => {
      window.removeEventListener('resize', handleResize);
      document.removeEventListener('touchstart', handleTouchStart);
      document.removeEventListener('touchend', handleTouchEnd);
    };
  }, [isOpen, toggleSidebar]);
  
  // Обеспечение правильной работы переключения сайдбара
  const handleToggleSidebar = useCallback(() => {
    if (toggleSidebar && typeof toggleSidebar === 'function') {
      toggleSidebar();
    }
  }, [toggleSidebar]);
  
  // Обработка нажатий на пункты меню (для мобильных)
  const handleMenuClick = useCallback(() => {
    if (isMobile && isOpen) {
      handleToggleSidebar();
    }
  }, [isMobile, isOpen, handleToggleSidebar]);
  
  // Language selector component is now commented out
  /* const LanguageSelector = () => (
    <div className="language-selector">
      <button
        type="button"
        className={`language-btn ${displayLanguage === 'ru' ? 'active' : ''}`}
        onClick={() => changeLanguage('ru')}
      >
        RU
      </button>
      <button
        type="button"
        className={`language-btn ${displayLanguage === 'kz' ? 'active' : ''}`}
        onClick={() => changeLanguage('kz')}
      >
        KZ
      </button>
      <button
        type="button"
        className={`language-btn ${displayLanguage === 'en' ? 'active' : ''}`}
        onClick={() => changeLanguage('en')}
      >
        EN
      </button>
    </div>
  ); */
  
  // Определение класса сайдбара на основе состояния
  const sidebarClass = `dashboard-sidebar ${isOpen ? 'open' : 'closed'} ${isCompact && !isMobile ? 'compact' : ''} ${className}`;
  
  return (
    <>
      {isOpen && isMobile && (
        <div 
          className={`sidebar-overlay ${isOpen ? 'visible' : ''}`} 
          onClick={handleToggleSidebar}
        ></div>
      )}
      <aside className={sidebarClass}>
        <div className="sidebar-logo-container">
          <Link to="/dashboard" className="sidebar-logo">
            <i className="bx bxs-diamond"></i>
            <span className="logo-text">
              <span className="logo-text-royal">Royal</span>
              <span className="logo-text-hub">Hub</span>
            </span>
          </Link>
          {isMobile && (
            <button className="sidebar-close" onClick={handleToggleSidebar} aria-label={getText({ 
              ru: 'Закрыть меню', 
              kz: 'Мәзірді жабу', 
              en: 'Close menu' 
            })}>
              <i className="bx bx-x"></i>
            </button>
          )}
        </div>
        
        {/* Remove language selector */}
        {/* <LanguageSelector /> */}
        
        <nav className="sidebar-nav">
          {menuSections.map((section, index) => (
            <div key={index} className="menu-section">
              <h3 className="section-title">{getText(section.title)}</h3>
              <ul className="menu-list">
                {section.items.map((item, itemIndex) => (
                  <li key={itemIndex} className="menu-item">
                    <NavLink 
                      to={item.to} 
                      className={({isActive}) => `menu-link ${isActive ? 'active' : ''}`}
                      onClick={handleMenuClick}
                      title={isCompact && !isMobile ? getText(item.text) : ''}
                    >
                      <i className={item.icon}></i>
                      <span>{getText(item.text)}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
};

export default DashboardSidebar; 