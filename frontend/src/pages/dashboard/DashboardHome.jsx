import { useState, useEffect } from 'react';
import { Link, useOutletContext, useNavigate } from 'react-router-dom';
import { useLanguage } from '../../contexts/LanguageContext';
import { translations } from '../../translations/translations';
import './styles.css'; // Make sure to create this file if it doesn't exist

// Helper to pluralize 'day' labels per language
const getDaysLabel = (days, t, language) => {
  if (language === 'ru') {
    const rem100 = days % 100;
    const rem10 = days % 10;
    if (rem100 >= 11 && rem100 <= 14) return 'дней';
    if (rem10 === 1) return 'день';
    if (rem10 >= 2 && rem10 <= 4) return 'дня';
    return 'дней';
  }
  if (language === 'en') {
    return days === 1 ? 'day' : 'days';
  }
  // For Kazakh and others, fallback to t.days
  return t.days;
};

const DashboardHome = () => {
  const daysLabel = (num) => getDaysLabel(num, t, language);
  const { profileData } = useOutletContext();
  const { language } = useLanguage();
  const navigate = useNavigate();
  const t = translations[language];
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Fetch subscription info
  useEffect(() => {
    const fetchSubscription = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch('/api/users/my/subscription', {
          credentials: 'include'
        });
        
        if (response.status === 401) {
          // Redirect to login if not authenticated
          navigate('/login');
          return;
        }
        
        if (!response.ok) {
          throw new Error();
        }
        
        let data;
        try {
          data = await response.json();
        } catch (parseError) {
          // If the response is not JSON, assume unauthorized
          navigate('/login');
          return;
        }
        
        if (data.status === 'ok') {
          setSubscription(data.data);
        } else {
          throw new Error();
        }
      } catch (err) {
        console.error('Error fetching subscription:', err);
        setError('Не удалось загрузить информацию о подписке');
      } finally {
        setLoading(false);
      }
    };
    
    fetchSubscription();
  }, []);
  
  // Format money with thousand separators and tenge symbol
  const formatMoney = (amount) => {
    return new Intl.NumberFormat('ru-KZ', {
      style: 'currency',
      currency: 'KZT',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount || 0);
  };
  
  const getSubscriptionColor = (type) => {
    switch(type?.toLowerCase()) {
      case 'royal':
        return 'from-amber-400 to-yellow-600';
      case 'vip':
        return 'from-blue-500 to-indigo-600';
      case 'economy':
        return 'from-green-500 to-emerald-600';
      case 'school':
        return 'from-purple-500 to-violet-600';
      case 'demo':
        return 'from-gray-400 to-gray-600';
      default:
        return 'from-gray-400 to-gray-600';
    }
  };

  const getSubscriptionIconColor = (type) => {
    switch(type?.toLowerCase()) {
      case 'royal':
        return {
          bg: 'bg-gradient-to-br from-amber-100 to-yellow-200 dark:from-amber-900/30 dark:to-yellow-800/30',
          text: 'text-amber-600 dark:text-amber-400'
        };
      case 'vip':
        return {
          bg: 'bg-gradient-to-br from-blue-100 to-indigo-200 dark:from-blue-900/30 dark:to-indigo-800/30',
          text: 'text-blue-600 dark:text-blue-400'
        };
      case 'economy':
        return {
          bg: 'bg-gradient-to-br from-green-100 to-emerald-200 dark:from-green-900/30 dark:to-emerald-800/30',
          text: 'text-green-600 dark:text-green-400'
        };
      case 'school':
        return {
          bg: 'bg-gradient-to-br from-purple-100 to-violet-200 dark:from-purple-900/30 dark:to-violet-800/30',
          text: 'text-purple-600 dark:text-purple-400'
        };
      default:
        return {
          bg: 'bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-900/30 dark:to-gray-800/30',
          text: 'text-gray-600 dark:text-gray-400'
        };
    }
  };

  return (
    <div className="space-y-6">
      {/* Welcome Section */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
        <div className="bg-gradient-to-r from-primary-600 to-primary-400 h-2"></div>
        <div className="p-6">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            {t.welcomeBack}, {profileData?.full_name}!
          </h1>
          <p className="text-gray-600 dark:text-gray-300">
            {t.dashboardWelcomeMessage}
          </p>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Balance Card */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
          <div className="h-2 bg-gradient-to-r from-emerald-400 to-green-500"></div>
          <div className="p-5">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">{t.balance}</p>
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white">{formatMoney(profileData?.money)}</h3>
              </div>
              <div className="h-12 w-12 rounded-full bg-gradient-to-br from-emerald-100 to-green-200 dark:from-emerald-900/30 dark:to-green-800/30 flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* Tests Completed */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
          <div className="h-2 bg-gradient-to-r from-primary-400 to-primary-600"></div>
          <div className="p-5">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">{t.testsCompleted}</p>
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white">0</h3>
              </div>
              <div className="h-12 w-12 rounded-full bg-gradient-to-br from-primary-100 to-primary-200 dark:from-primary-900/30 dark:to-primary-800/30 flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-primary-600 dark:text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* Average Score */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
          <div className="h-2 bg-gradient-to-r from-blue-400 to-indigo-500"></div>
          <div className="p-5">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">{t.averageScore}</p>
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white">0%</h3>
              </div>
              <div className="h-12 w-12 rounded-full bg-gradient-to-br from-blue-100 to-indigo-200 dark:from-blue-900/30 dark:to-indigo-800/30 flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* Subscription */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
          <div className={`h-2 bg-gradient-to-r ${
            subscription?.has_subscription 
              ? getSubscriptionColor(subscription.subscription_type)
              : 'from-gray-400 to-gray-600'
          }`}></div>
          <div className="p-5">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">{t.subscriptionStatus}</p>
                {loading ? (
                  <div className="h-6 w-24 bg-gray-200 dark:bg-gray-700 rounded animate-pulse mt-1"></div>
                ) : error ? (
                  <p className="text-red-500 mt-1">{error}</p>
                ) : (
                  <div className="mt-2">
                    <h3 className="text-2xl font-bold text-gray-900 dark:text-white capitalize">
                      {subscription?.has_subscription ? (
                        subscription.subscription_type
                      ) : (
                        t.noSubscription
                      )}
                    </h3>
                    {subscription?.has_subscription && (
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        {`До окончания: ${subscription.days_left} ${daysLabel(subscription.days_left)}`}
                      </p>
                    )}
                  </div>
                )}
              </div>
              <div>
                {subscription?.has_subscription ? (
                  <div className={`h-12 w-12 rounded-full flex items-center justify-center ${getSubscriptionIconColor(subscription.subscription_type).bg}`}>
                    <svg xmlns="http://www.w3.org/2000/svg" className={`h-6 w-6 ${getSubscriptionIconColor(subscription.subscription_type).text}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                    </svg>
                  </div>
                ) : (
                  <div className="h-12 w-12 rounded-full bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-900/30 dark:to-gray-800/30 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-gray-600 dark:text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                    </svg>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity and Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Tests */}
        <div className="lg:col-span-2 bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
          <div className="h-2 bg-gradient-to-r from-primary-400 to-primary-600"></div>
          <div className="p-6">
            <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4">{t.recentTests}</h2>
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden">
              <div className="p-4 text-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mx-auto text-gray-400 dark:text-gray-500 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                <p className="text-gray-600 dark:text-gray-400">{t.noRecentTests}</p>
                <button 
                  onClick={() => navigate('/dashboard/tests')}
                  className="mt-4 px-6 py-2.5 bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-600 hover:to-primary-700 text-white rounded-lg font-medium shadow-sm hover:shadow transition-all"
                >
                  {t.startFirstTest}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
          <div className="h-2 bg-gradient-to-r from-indigo-400 to-purple-500"></div>
          <div className="p-6">
            <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4">{t.quickActions}</h2>
            <div className="space-y-3">
              <Link to="/dashboard/tests" className="w-full bg-gradient-to-r from-primary-500 to-primary-600 text-white py-3 rounded-lg font-medium hover:from-primary-600 hover:to-primary-700 transition-colors flex items-center justify-center space-x-2 shadow-sm hover:shadow">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                <span>{t.startNewTest}</span>
              </Link>
              <Link to="/dashboard/referrals" className="w-full bg-gradient-to-r from-blue-500 to-indigo-600 text-white py-3 rounded-lg font-medium hover:from-blue-600 hover:to-indigo-700 transition-colors flex items-center justify-center space-x-2 shadow-sm hover:shadow">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                <span>{t.inviteFriend}</span>
              </Link>
              <Link to="/dashboard/subscription" className="w-full bg-gradient-to-r from-amber-500 to-yellow-500 text-white py-3 rounded-lg font-medium hover:from-amber-600 hover:to-yellow-600 transition-colors flex items-center justify-center space-x-2 shadow-sm hover:shadow">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                </svg>
                <span>{t.upgradeAccount}</span>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardHome; 