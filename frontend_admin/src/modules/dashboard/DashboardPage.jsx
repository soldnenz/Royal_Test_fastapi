import React, { useState, useEffect, useCallback } from 'react';
import DashboardHeader from './DashboardHeader';
import DashboardSidebar from './DashboardSidebar';
import StatsGrid from './StatsGrid';
import ChartsGrid from './charts/ChartsGrid';
import './DashboardPage.css';
import { useLoader } from '../../shared/LoaderContext';

const DashboardPage = ({ noLayout = false }) => {
  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth > 1024);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 1024);
  const [isCompact, setIsCompact] = useState(window.innerWidth <= 1200 && window.innerWidth > 1024);
  const { show, hide } = useLoader();
  
  // Toggle sidebar with stable function reference
  const toggleSidebar = useCallback(() => {
    setSidebarOpen(prevState => !prevState);
    // Force layout recalculation on mobile
    if (window.innerWidth <= 1024) {
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
      }, 50);
    }
  }, []);
  
  // Initialize sidebar state based on screen width
  useEffect(() => {
    // Skip initialization if using external layout
    if (noLayout) return;
    
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
    
    // Call on mount
    handleResize();
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [sidebarOpen, noLayout]);
  
  // Simulate data loading if needed
  const fetchDashboardData = async () => {
    show(); // Show loading indicator
    try {
      // Simulate API request
      await new Promise(resolve => setTimeout(resolve, 1500));
      // Here would be actual data loading
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      hide(); // Hide loading indicator
    }
  };

  const contentClass = `dashboard-content ${!sidebarOpen ? 'sidebar-closed' : ''} ${isCompact && sidebarOpen && !isMobile ? 'sidebar-compact' : ''}`;

  // If using external layout, only display content
  if (noLayout) {
    return (
      <>
        <StatsGrid />
        <ChartsGrid />
      </>
    );
  }

  // Otherwise use full layout with sidebar and header
  return (
    <div className="dashboard-container">
      <DashboardSidebar isOpen={sidebarOpen} toggleSidebar={toggleSidebar} />
      <div className={contentClass}>
        <DashboardHeader 
          userName="Admin" 
          toggleSidebar={toggleSidebar} 
          isMobile={isMobile}
          sidebarOpen={sidebarOpen}
        />
        <main className="dashboard-main">
          <StatsGrid />
          <ChartsGrid />
        </main>
      </div>
    </div>
  );
};

export default DashboardPage; 