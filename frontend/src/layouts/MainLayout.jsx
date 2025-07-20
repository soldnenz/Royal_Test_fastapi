import { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import Header from '../components/Header';
import Footer from '../components/Footer';
import { handleReferralFromUrl } from '../utils/referralHelper';

const MainLayout = () => {
  // Check for referral code in URL on every page load
  useEffect(() => {
    handleReferralFromUrl();
  }, []);

  return (
    <div className="flex flex-col min-h-screen bg-gray-50 dark:bg-gray-900">
      <Header />
      <main className="flex-grow">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
};

export default MainLayout; 