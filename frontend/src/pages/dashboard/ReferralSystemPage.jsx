import React, { useState, useEffect } from 'react';
import { useLanguage } from '../../contexts/LanguageContext';
import { translations } from '../../translations/translations';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';
import './styles.css';

const ReferralSystemPage = () => {
  const { language } = useLanguage();
  const { isDarkMode } = useTheme();
  const t = translations[language];
  
  const [loading, setLoading] = useState(true);
  const [referralCode, setReferralCode] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [description, setDescription] = useState('');
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [subscription, setSubscription] = useState(null);
  const [statistics, setStatistics] = useState({
    totalEarned: 0,
    totalRegistered: 0,
    totalPurchased: 0,
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      // Fetch user's subscription status
      const subResponse = await fetch('/api/users/my/subscription', {
        credentials: 'include'
      });
      
      if (subResponse.ok) {
        const result = await subResponse.json();
        if (result.status === "ok" && result.data) {
          setSubscription(result.data);
        }
      }

      // Try to fetch existing referral code
      try {
        const referralResponse = await fetch('/api/referrals/my', {
          credentials: 'include'
        });
        
        if (referralResponse.ok) {
          const result = await referralResponse.json();
          if (result.status === "ok" && result.data) {
            setReferralCode(result.data);
            
            // Fetch referral transactions
            const transactionsResponse = await fetch('/api/referrals/transactions', {
              credentials: 'include'
            });
            
            if (transactionsResponse.ok) {
              const transResult = await transactionsResponse.json();
              if (transResult.status === "ok" && transResult.data) {
                setTransactions(transResult.data.transactions || []);
                setStatistics({
                  totalEarned: transResult.data.totalEarned || 0,
                  totalRegistered: transResult.data.totalRegistered || 0,
                  totalPurchased: transResult.data.totalPurchased || 0,
                });
              }
            }
          }
        } else if (referralResponse.status === 404) {
          // No referral code exists yet
          setReferralCode(null);
        } else {
          throw new Error('Failed to fetch referral code');
        }
      } catch (error) {
        // No referral code exists yet
        console.error('Error fetching referral code:', error);
        setReferralCode(null);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error(t.failedToLoadReferralData || 'Не удалось загрузить данные реферальной системы');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateReferral = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/referrals/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          description: description || t.myReferralProgram || 'Моя реферальная программа'
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        if (result.status === "ok" && result.data) {
          setReferralCode(result.data);
          toast.success(t.referralCodeCreatedSuccess || 'Реферальный код успешно создан!');
          setCreateModalVisible(false);
        } else {
          throw new Error(result.message || 'Error creating referral code');
        }
      } else {
        throw new Error('Failed to create referral code');
      }
    } catch (error) {
      console.error('Error creating referral code:', error);
      toast.error(t.failedToCreateReferralCode || 'Не удалось создать реферальный код');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      toast.success(t.copiedToClipboard || 'Скопировано в буфер обмена!');
    }).catch(() => {
      toast.error(t.failedToCopyText || 'Не удалось скопировать текст');
    });
  };

  // Updated to include Economy subscription
  const canCreateReferral = () => {
    if (!subscription || !subscription.has_subscription) return false;
    return ['economy', 'vip', 'royal'].includes(subscription.subscription_type?.toLowerCase());
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    
    const date = new Date(dateString);
    const options = { 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    };
    
    // Use the appropriate locale based on the selected language
    let locale = 'ru-RU';
    if (language === 'en') {
      locale = 'en-US';
    } else if (language === 'kz') {
      locale = 'kk-KZ';
    }
    
    return date.toLocaleDateString(locale, options);
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

  const getReferralUrl = () => {
    return `${window.location.origin}/registration?ref=${referralCode?.code}`;
  };

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">
        {t.referralSystem || 'Реферальная система'}
      </h1>
      <p className="text-gray-600 dark:text-gray-300 mb-6">
        {t.referralSystemDesc || 'Приглашайте друзей и получайте бонусы за их покупки.'}
      </p>

      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
        </div>
      ) : (
        <>
          {referralCode ? (
            <>
              {/* Neon gradient border wrapper */}
              <div className="gold-border mb-6">
                <div className="relative bg-white dark:bg-gray-800 rounded-lg p-6 text-center space-y-4 transform transition-shadow duration-300 hover:shadow-[0_0_15px_rgba(255,215,0,0.7),0_0_30px_rgba(255,193,7,0.5)]">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                    {t.yourReferralCode || "Ваш реферальный код"}
                  </h2>
                  <div className="flex justify-center items-center">
                    <input
                      type="text"
                      value={getReferralUrl()}
                      readOnly
                      className="w-full max-w-lg text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 px-4 py-2 rounded-l-md border border-gray-300 dark:border-gray-600"
                    />
                    <button
                      onClick={() => copyToClipboard(getReferralUrl())}
                      className="px-4 py-2 bg-yellow-500 text-gray-900 rounded-r-md hover:bg-yellow-600 transition-colors"
                    >
                      {t.copy || "Скопировать"}
                    </button>
                  </div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t.rewardRate || "Ставка вознаграждения"}: {referralCode.rate.value}%
                  </p>
                  {/* Styled referral code card with gradient border wrapper */}
                  <div className="mx-auto max-w-sm gradient-border mb-6">
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-xl flex items-center justify-between">
                      <span className="text-3xl font-mono font-semibold text-gray-900 dark:text-white select-text">
                        {referralCode.code}
                      </span>
                      <button
                        onClick={() => copyToClipboard(referralCode.code)}
                        title={t.copyCode || "Скопировать код"}
                        className="ml-4 px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-white rounded-lg transition-colors"
                      >
                        {t.copyCode || "Скопировать"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Statistics Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
                  <div className="p-5">
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {t.totalEarned || "Всего заработано"}
                        </p>
                        <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
                          {formatMoney(statistics.totalEarned)}
                        </h3>
                      </div>
                      <div className="h-12 w-12 rounded-full bg-gradient-to-br from-primary-100 to-primary-200 dark:from-primary-900/30 dark:to-primary-800/30 flex items-center justify-center">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-primary-600 dark:text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
                
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
                  <div className="p-5">
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {t.usersAttracted || "Привлечено пользователей"}
                        </p>
                        <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
                          {statistics.totalRegistered}
                        </h3>
                      </div>
                      <div className="h-12 w-12 rounded-full bg-gradient-to-br from-blue-100 to-blue-200 dark:from-blue-900/30 dark:to-blue-800/30 flex items-center justify-center">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
                
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
                  <div className="p-5">
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {t.madePurchases || "Совершили покупку"}
                        </p>
                        <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
                          {statistics.totalPurchased}
                        </h3>
                      </div>
                      <div className="h-12 w-12 rounded-full bg-gradient-to-br from-green-100 to-green-200 dark:from-green-900/30 dark:to-green-800/30 flex items-center justify-center">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Referral Users Table */}
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
                <div className="p-6">
                  <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
                    {t.referralUsersList || "Список реферальных пользователей"}
                  </h2>
                  
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                      <thead className="bg-gray-50 dark:bg-gray-700">
                        <tr>
                          <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                            {t.iin || 'ИИН'}
                          </th>
                          <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                            {t.fullName || 'ФИО'}
                          </th>
                          <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                            {t.registrationDate || 'Дата регистрации'}
                          </th>
                          <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                            {t.status || 'Статус'}
                          </th>
                          <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                            {t.earned || 'Заработано'}
                          </th>
                          <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                            {t.transactionDate || 'Дата транзакции'}
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                        {transactions.length > 0 ? (
                          transactions.map((transaction) => (
                            <tr key={transaction.id}>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                {transaction.user_iin}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                                {transaction.user_name}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                {formatDate(transaction.registration_date)}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                {transaction.has_purchased ? (
                                  <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400">
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
                                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                    </svg>
                                    {t.madePurchase || 'Сделал покупку'}
                                  </span>
                                ) : (
                                  <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-400">
                                    {t.waitingForPurchase || 'Ожидает покупки'}
                                  </span>
                                )}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                {formatMoney(transaction.amount)}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                {transaction.transaction_date ? formatDate(transaction.transaction_date) : '-'}
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan="6" className="px-6 py-4 text-center text-sm text-gray-500 dark:text-gray-400">
                              {t.noOneUsedYourCode || 'Пока никто не воспользовался вашим реферальным кодом'}
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
              <div className="p-6">
                {canCreateReferral() ? (
                  <>
                    <div className="mb-6 bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-400 dark:border-blue-600 p-4 rounded">
                      <div className="flex">
                        <div className="flex-shrink-0">
                          <svg className="h-5 w-5 text-blue-400 dark:text-blue-300" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <div className="ml-3">
                          <h3 className="text-sm font-medium text-blue-800 dark:text-blue-300">
                            {t.noReferralCode || "У вас нет реферального кода"}
                          </h3>
                          <div className="mt-2 text-sm text-blue-700 dark:text-blue-400">
                            <p>{t.createReferralCodeDesc || "Создайте реферальный код, чтобы начать зарабатывать на приглашенных пользователях."}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                    <button 
                      onClick={() => setCreateModalVisible(true)}
                      className="px-4 py-2 bg-primary-500 text-white rounded-md hover:bg-primary-600 transition-colors"
                    >
                      {t.createReferralCode || "Создать реферальный код"}
                    </button>
                  </>
                ) : (
                  <div className="bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-400 dark:border-yellow-600 p-4 rounded">
                    <div className="flex">
                      <div className="flex-shrink-0">
                        <svg className="h-5 w-5 text-yellow-400 dark:text-yellow-300" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <div className="ml-3">
                        <h3 className="text-sm font-medium text-yellow-800 dark:text-yellow-300">
                          {t.referralSystemUnavailable || "Реферальная система недоступна"}
                        </h3>
                        <div className="mt-2 text-sm text-yellow-700 dark:text-yellow-400">
                          <p>{t.needSubscriptionForReferral || "Для создания реферального кода необходимо иметь активную подписку Economy, VIP или Royal."}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Create Referral Modal */}
          {createModalVisible && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 w-full max-w-md">
                <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
                  {t.createReferralCodeTitle || "Создание реферального кода"}
                </h3>
                <p className="text-gray-600 dark:text-gray-300 mb-4">
                  {t.specifyReferralDesc || "Укажите описание для вашего реферального кода:"}
                </p>
                <input
                  type="text"
                  placeholder={t.descriptionOptional || "Описание (необязательно)"}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white mb-4"
                />
                <div className="flex justify-end space-x-2">
                  <button
                    onClick={() => setCreateModalVisible(false)}
                    className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  >
                    {t.cancel || "Отмена"}
                  </button>
                  <button
                    onClick={handleCreateReferral}
                    disabled={loading}
                    className={`px-4 py-2 bg-primary-500 text-white rounded-md hover:bg-primary-600 transition-colors ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {loading ? (
                      <span className="flex items-center">
                        <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        {t.creating || "Создание..."}
                      </span>
                    ) : (
                      t.create || "Создать"
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ReferralSystemPage; 