import React, { useState, useEffect } from 'react';
import { useLanguage } from '../../contexts/LanguageContext';
import { useTheme } from '../../contexts/ThemeContext';
import { translations } from '../../translations/translations';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { FaUser, FaEnvelope, FaPhone, FaIdCard, FaWallet, FaCalendarAlt, FaArrowUp, FaArrowDown, FaGift, FaTags, FaUserFriends } from 'react-icons/fa';
import axios from 'axios';
import './styles.css';

const ProfilePage = () => {
  const { language } = useLanguage();
  const { isDarkMode } = useTheme();
  const t = translations[language];
  
  const [profile, setProfile] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [transactionsLoading, setTransactionsLoading] = useState(true);
  
  useEffect(() => {
    fetchProfile();
    fetchTransactions();
  }, []);
  
  const fetchProfile = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/users/me', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const result = await response.json();
        if (result.status === "ok" && result.data) {
          setProfile(result.data);
        } else {
          throw new Error(result.message || 'Failed to fetch profile');
        }
      } else {
        throw new Error('Failed to fetch profile');
      }
    } catch (error) {
      console.error('Error fetching profile:', error);
      toast.error(t.errorFetchingProfile || 'Error fetching profile');
    } finally {
      setLoading(false);
    }
  };
  
  const fetchTransactions = async () => {
    try {
      setTransactionsLoading(true);
      const response = await fetch('/api/users/my/transactions', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const result = await response.json();
        if (result.status === "ok" && result.data) {
          setTransactions(result.data.transactions || []);
        } else {
          throw new Error(result.message || 'Failed to fetch transactions');
        }
      } else {
        throw new Error('Failed to fetch transactions');
      }
    } catch (error) {
      console.error('Error fetching transactions:', error);
      toast.error(t.errorFetchingTransactions || 'Error fetching transactions');
    } finally {
      setTransactionsLoading(false);
    }
  };
  
  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString(language === 'ru' ? 'ru-RU' : language === 'kz' ? 'kk-KZ' : 'en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };
  
  const formatDateTime = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleString(
      language === 'ru' ? 'ru-RU' : language === 'kz' ? 'kk-KZ' : 'en-US',
      { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }
    );
  };
  
  const formatMoney = (amount) => {
    if (amount === null || amount === undefined) return '-';
    return new Intl.NumberFormat(language === 'en' ? 'en-US' : language === 'kz' ? 'kk-KZ' : 'ru-KZ', {
      style: 'currency',
      currency: 'KZT',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };
  
  const getTransactionTypeIcon = (type) => {
    switch(type) {
      case 'subscription_purchase':
        return <FaWallet className="text-blue-500 dark:text-blue-400" />;
      case 'promo_code_purchase':
        return <FaTags className="text-purple-500 dark:text-purple-400" />;
      case 'gift_subscription':
        return <FaGift className="text-pink-500 dark:text-pink-400" />;
      case 'referral':
        return <FaUserFriends className="text-green-500 dark:text-green-400" />;
      default:
        return <FaWallet className="text-gray-500 dark:text-gray-400" />;
    }
  };
  
  const getTransactionTypeLabel = (type) => {
    switch(type) {
      case 'subscription_purchase':
        return t.subscriptionPurchase || 'Покупка подписки';
      case 'promo_code_purchase':
        return t.promoCodePurchase || 'Покупка промокода';
      case 'gift_subscription':
        return t.giftSubscription || 'Подарочная подписка';
      case 'referral':
        return t.referralBonus || 'Реферальный бонус';
      default:
        return type;
    }
  };
  
  const renderProfile = () => {
    if (!profile) return null;
    
    return (
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg overflow-hidden border border-gray-200 dark:border-gray-700">
        <div className="bg-gradient-to-r from-amber-500 to-yellow-600 px-6 py-5">
          <h2 className="text-2xl font-bold text-white">{t.myProfile || 'My Profile'}</h2>
        </div>
        
        <div className="p-6">
          <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
            <div className="flex-shrink-0 bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 p-6 rounded-full">
              <FaUser size={48} />
            </div>
            
            <div className="flex-grow">
              <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-1">{profile.full_name}</h3>
              <p className="text-gray-500 dark:text-gray-400">{t.memberSince || 'Пользователь с'} {formatDate(profile.created_at)}</p>
              
              <div className="bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-400 px-3 py-1 rounded-full inline-flex items-center mt-3">
                <FaWallet className="mr-1" />
                <span className="font-medium">{formatMoney(profile.money)}</span>
              </div>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
            <div className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
              <div className="flex items-center">
                <div className="flex-shrink-0 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 p-2 rounded-full mr-3">
                  <FaEnvelope />
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{t.email || 'Email'}</p>
                  <p className="text-gray-900 dark:text-white font-medium">{profile.email || '-'}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
              <div className="flex items-center">
                <div className="flex-shrink-0 bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 p-2 rounded-full mr-3">
                  <FaPhone />
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{t.phone || 'Телефон'}</p>
                  <p className="text-gray-900 dark:text-white font-medium">{profile.phone || '-'}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
              <div className="flex items-center">
                <div className="flex-shrink-0 bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 p-2 rounded-full mr-3">
                  <FaIdCard />
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{t.iin || 'ИИН'}</p>
                  <p className="text-gray-900 dark:text-white font-medium">{profile.iin || '-'}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
              <div className="flex items-center">
                <div className="flex-shrink-0 bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 p-2 rounded-full mr-3">
                  <FaCalendarAlt />
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{t.registrationDate || 'Дата регистрации'}</p>
                  <p className="text-gray-900 dark:text-white font-medium">{formatDate(profile.created_at) || '-'}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };
  
  const renderTransactionsList = () => {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg overflow-hidden border border-gray-200 dark:border-gray-700 mt-6">
        <div className="bg-gradient-to-r from-blue-500 to-indigo-600 px-6 py-5">
          <h2 className="text-2xl font-bold text-white">{t.myTransactions || 'My Transactions'}</h2>
        </div>
        
        {transactionsLoading ? (
          <div className="p-6 flex justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
          </div>
        ) : transactions.length === 0 ? (
          <div className="p-6 text-center">
            <div className="mb-4">
              <FaWallet className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500" />
            </div>
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-1">{t.noTransactions || 'No Transactions'}</h3>
            <p className="text-gray-500 dark:text-gray-400">{t.noTransactionsYet || 'You don\'t have any transactions yet'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                    {t.type || 'Тип'}
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                    {t.date || 'Дата'}
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                    {t.amount || 'Сумма'}
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                    {t.description || 'Описание'}
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                {transactions.map((transaction, index) => (
                  <tr key={index} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-10 w-10 flex items-center justify-center">
                          {getTransactionTypeIcon(transaction.type)}
                        </div>
                        <div className="ml-4">
                          <div className="text-sm font-medium text-gray-900 dark:text-white">
                            {getTransactionTypeLabel(transaction.type)}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {formatDateTime(transaction.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium ${
                        transaction.amount > 0
                          ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400'
                          : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400'
                      }`}>
                        {transaction.amount > 0 ? <FaArrowUp className="mr-1" /> : <FaArrowDown className="mr-1" />}
                        {formatMoney(Math.abs(transaction.amount))}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                      {transaction.description}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  };
  
  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen p-4">
        <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-primary-500"></div>
      </div>
    );
  }
  
  return (
    <div className="p-4">
      {renderProfile()}
      {renderTransactionsList()}
      
      <ToastContainer
        position="top-right"
        autoClose={5000}
        hideProgressBar={false}
        newestOnTop
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
        theme="colored"
      />
    </div>
  );
};

export default ProfilePage; 