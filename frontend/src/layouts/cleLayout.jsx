import { Outlet } from 'react-router-dom';
import Header from '../components_cle/Header_cle';
import Footer from '../components_cle/Footer_cle';

const cleLayout = () => {
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

export default cleLayout; 