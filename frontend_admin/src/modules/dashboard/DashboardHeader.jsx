import React, { useState, useRef, useEffect } from 'react';
import './DashboardHeader.css';

const DashboardHeader = ({ userName, toggleSidebar, isMobile, sidebarOpen }) => {
  const [isDarkMode, setIsDarkMode] = useState(localStorage.getItem('theme') === 'dark');
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const dropdownRef = useRef(null);
  const isClickingInside = useRef(false);
  
  const toggleDarkMode = () => {
    const newMode = !isDarkMode;
    setIsDarkMode(newMode);
    
    if (newMode) {
      document.body.classList.add('dark-theme');
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.body.classList.remove('dark-theme');
      document.documentElement.setAttribute('data-theme', 'light');
      localStorage.setItem('theme', 'light');
    }
  };
  
  const handleToggleSidebar = () => {
    if (typeof toggleSidebar === 'function') {
      toggleSidebar();
    }
  };
  
  const toggleProfileMenu = () => {
    console.log('Toggle clicked, current state:', showProfileMenu);
    setShowProfileMenu(prev => {
      console.log('Setting showProfileMenu to:', !prev);
      return !prev;
    });
  };

  const handleLogout = async () => {
    try {
      const response = await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include'
      });

      if (response.ok) {
        // Очищаем локальное хранилище
        localStorage.clear();
        sessionStorage.clear();
        
        // Перенаправляем на страницу входа или главную
        window.location.href = '/';
      } else {
        console.error('Logout failed');
        alert('Ошибка при выходе из системы');
      }
    } catch (error) {
      console.error('Error during logout:', error);
      alert('Ошибка при выходе из системы');
    }
  };

  // Обработчики для dropdown
  const handleDropdownMouseDown = () => {
    isClickingInside.current = true;
  };

  const handleDropdownMouseUp = () => {
    isClickingInside.current = false;
  };

  // Закрытие dropdown при клике вне элемента
  useEffect(() => {
    console.log('showProfileMenu changed to:', showProfileMenu);
    
    const handleDocumentClick = (event) => {
      if (!isClickingInside.current && dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowProfileMenu(false);
      }
      isClickingInside.current = false;
    };

    document.addEventListener('mousedown', handleDocumentClick);
    
    return () => {
      document.removeEventListener('mousedown', handleDocumentClick);
    };
  }, []);
  
  return (
    <header className="dashboard-header glass-header">
      <div className="header-left">
        {isMobile && (
          <button 
            className="mobile-toggle icon-btn" 
            onClick={handleToggleSidebar} 
            aria-label="Переключить меню"
          >
            <i className='bx bx-menu'></i>
          </button>
        )}
        <div className="header-search">
          <i className='bx bx-search'></i>
          <input type="text" placeholder="Поиск..." />
        </div>
      </div>
      
      <div className="header-right">
        <button className="icon-btn" onClick={toggleDarkMode} title={isDarkMode ? "Светлая тема" : "Тёмная тема"}>
          <i className={`bx ${isDarkMode ? 'bx-sun' : 'bx-moon'}`}></i>
        </button>
        
        <button className="icon-btn notification-btn" aria-label="Уведомления" title="Уведомления">
          <i className='bx bx-bell'></i>
          <span className="notification-badge">3</span>
        </button>

        <div 
          className="profile-dropdown" 
          ref={dropdownRef}
          onMouseDown={handleDropdownMouseDown}
          onMouseUp={handleDropdownMouseUp}
        >
          <button 
            className="icon-btn profile-btn" 
            aria-label="Профиль" 
            onClick={toggleProfileMenu} 
            title="Профиль"
          >
            <i className='bx bx-user'></i>
          </button>
          
          {showProfileMenu && (
            <div className="dropdown-menu">
              <div className="profile-info">
                <i className='bx bx-user-circle'></i>
                <div className="user-name">{userName || 'Админ'}</div>
              </div>
              <button className="dropdown-item" onClick={() => setShowProfileMenu(false)}>
                <i className='bx bx-user'></i>
                Профиль
              </button>
              <button className="dropdown-item" onClick={() => setShowProfileMenu(false)}>
                <i className='bx bx-cog'></i>
                Настройки
              </button>
              <div className="dropdown-divider"></div>
              <button className="dropdown-item text-danger" onClick={handleLogout}>
                <i className='bx bx-log-out'></i>
                Выйти
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default DashboardHeader; 