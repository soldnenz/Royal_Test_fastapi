import React, { useState, useEffect, useCallback } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import DashboardPage from './modules/dashboard/DashboardPage';
import UsersPage from './modules/users/UsersPage';
import TestsPage from './modules/tests/TestsPage';
import DashboardSidebar from './modules/dashboard/DashboardSidebar';
import DashboardHeader from './modules/dashboard/DashboardHeader';
import './App.css';

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth > 1024);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 1024);
  const [isCompact, setIsCompact] = useState(window.innerWidth <= 1200 && window.innerWidth > 1024);
  
  // Use useCallback for toggleSidebar to maintain reference stability
  const toggleSidebar = useCallback(() => {
    setSidebarOpen(prevState => !prevState);
    // Force layout recalculation on mobile
    if (window.innerWidth <= 1024) {
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
      }, 50);
    }
  }, []);
  
  // Initialize sidebar state based on screen width and check for theme
  useEffect(() => {
    // Check and apply saved theme
    const savedTheme = localStorage.getItem('theme') || 'light';
    
    if (savedTheme === 'dark') {
      document.body.classList.add('dark-theme');
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.body.classList.remove('dark-theme');
      document.documentElement.setAttribute('data-theme', 'light');
      localStorage.setItem('theme', 'light');
    }
    
    const handleResize = () => {
      const mobileView = window.innerWidth <= 1024;
      const compactView = window.innerWidth <= 1200 && window.innerWidth > 1024;
      
      setIsMobile(mobileView);
      setIsCompact(compactView);
      
      // Only auto-adjust sidebar on non-mobile
      if (!mobileView && !sidebarOpen) {
        setSidebarOpen(true);
      }
    };
    
    // Call handleResize initially
    handleResize();
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [sidebarOpen]);

  const sidebarClass = sidebarOpen ? (isCompact ? "compact" : "") : "closed";
  const contentClass = `dashboard-content ${!sidebarOpen ? 'sidebar-closed' : ''} ${isCompact && sidebarOpen && !isMobile ? 'sidebar-compact' : ''}`;

  return (
    <div className="dashboard-container">
      <DashboardSidebar 
        isOpen={sidebarOpen} 
        toggleSidebar={toggleSidebar} 
        className={sidebarClass}
      />
      <div className={contentClass}>
        <DashboardHeader 
          userName="Admin" 
          toggleSidebar={toggleSidebar} 
          isMobile={isMobile}
          sidebarOpen={sidebarOpen}
        />
        <main className="dashboard-main">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage noLayout={true} />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/tests" element={<TestsPage />} />
            <Route path="/settings" element={<div className="content-section active">Настройки системы</div>} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default App;
