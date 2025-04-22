import { useState, useEffect } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';
import { translations } from '../translations/translations';
import DashboardSidebar from '../components/dashboard/DashboardSidebar';
import DashboardHeader from '../components/dashboard/DashboardHeader';

const DashboardLayout = () => {
  const { language } = useLanguage();
  const navigate = useNavigate();
  const t = translations[language];
  const [profileData, setProfileData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // Fetch user profile data
  useEffect(() => {
    const fetchProfileData = async () => {
      try {
        setIsLoading(true);
        const response = await fetch('/api/users/me', {
          credentials: 'include'
        });

        if (!response.ok) {
          if (response.status === 401) {
            // Redirect to login if not authenticated
            navigate('/login');
            return;
          }
          throw new Error('Failed to fetch profile data');
        }

        const data = await response.json();
        if (data.status === "ok") {
          setProfileData(data.data);
        } else {
          throw new Error(data.message || 'Unknown error');
        }
      } catch (err) {
        setError(err.message);
        console.error('Error fetching profile:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchProfileData();
  }, [navigate]);

  // Toggle sidebar visibility (especially for mobile)
  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  // If loading or no profile data available yet, show loading state
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <svg className="animate-spin h-12 w-12 text-primary-500 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
          <p className="text-lg text-gray-700 dark:text-gray-300">{t.loading}</p>
        </div>
      </div>
    );
  }

  // If there was an error fetching the profile
  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center max-w-md p-6 bg-white dark:bg-gray-800 rounded-lg shadow-lg">
          <div className="text-red-500 text-5xl mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="w-16 h-16 mx-auto">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">{t.errorOccurred}</h2>
          <p className="text-gray-600 dark:text-gray-400 mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors"
          >
            {t.tryAgain}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* Sidebar */}
      <DashboardSidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />

      {/* Main Content */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Header */}
        <DashboardHeader 
          profileData={profileData} 
          toggleSidebar={toggleSidebar}
        />

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <div className="container mx-auto">
            <Outlet context={{ profileData }} />
          </div>
        </main>
      </div>
    </div>
  );
};

export default DashboardLayout; 