import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useLanguage } from '../../contexts/LanguageContext';
import { translations } from '../../translations/translations';

const SubscriptionPage = () => {
  const { profileData } = useOutletContext();
  const { language } = useLanguage();
  const t = translations[language];
  
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('subscription');
  const [amount, setAmount] = useState('');
  const [promoCode, setPromoCode] = useState('');
  const [iinValue, setIinValue] = useState('');
  const [selectedSubscriptionType, setSelectedSubscriptionType] = useState('Vip');
  const [selectedDuration, setSelectedDuration] = useState(1);
  const [isForGift, setIsForGift] = useState(false);
  
  // Fetch subscription info
  useEffect(() => {
    const fetchSubscription = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/users/my/subscription', {
          credentials: 'include'
        });
        
        if (response.ok) {
          const data = await response.json();
          if (data.status === 'ok') {
            setSubscription(data.data);
          } else {
            setError(data.message);
          }
        } else {
          throw new Error('Failed to fetch subscription data');
        }
      } catch (error) {
        console.error('Error fetching subscription:', error);
        setError(error.message);
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
  
  // Get subscription price based on type and duration
  const getSubscriptionPrice = (type, months) => {
    const basePrice = {
      'economy': 5000,
      'Vip': 10000,
      'Royal': 15000
    };
    
    // Discount for longer subscriptions
    const discountMultiplier = months === 3 ? 0.9 : months === 6 ? 0.85 : months === 12 ? 0.75 : 1;
    
    return Math.round(basePrice[type] * months * discountMultiplier);
  };
  
  // Handle subscription purchase
  const handlePurchaseSubscription = async (event) => {
    event.preventDefault();
    // Implementation would connect to payment gateway
    alert(`Purchase ${selectedSubscriptionType} subscription for ${selectedDuration} month(s) - ${formatMoney(getSubscriptionPrice(selectedSubscriptionType, selectedDuration))}`);
  };
  
  // Handle gift subscription/promo code purchase
  const handlePurchaseGift = async (event) => {
    event.preventDefault();
    // Implementation would connect to payment gateway
    alert(`Purchase gift ${selectedSubscriptionType} subscription for ${selectedDuration} month(s) - ${formatMoney(getSubscriptionPrice(selectedSubscriptionType, selectedDuration))}`);
  };
  
  // Handle balance top-up
  const handleTopUp = async (event) => {
    event.preventDefault();
    // Implementation would connect to payment gateway
    alert(`Top up balance with ${formatMoney(amount)}`);
  };
  
  // Handle promo code activation
  const handleActivatePromo = async (event) => {
    event.preventDefault();
    alert(`Activating promo code: ${promoCode}`);
  };
  
  // Handle gift by IIN
  const handleGiftByIIN = async (event) => {
    event.preventDefault();
    alert(`Sending gift to IIN: ${iinValue}`);
  };
  
  const getSubscriptionColor = (type) => {
    switch(type?.toLowerCase()) {
      case 'royal':
        return {
          gradient: 'from-amber-400 to-yellow-600',
          bg: 'bg-gradient-to-r from-amber-500 to-yellow-500',
          bgHover: 'hover:from-amber-600 hover:to-yellow-600',
          border: 'border-amber-300',
          text: 'text-amber-700 dark:text-amber-300'
        };
      case 'vip':
        return {
          gradient: 'from-blue-500 to-indigo-600',
          bg: 'bg-gradient-to-r from-blue-500 to-indigo-600',
          bgHover: 'hover:from-blue-600 hover:to-indigo-700',
          border: 'border-blue-300',
          text: 'text-blue-700 dark:text-blue-300'
        };
      case 'economy':
        return {
          gradient: 'from-green-500 to-emerald-600',
          bg: 'bg-gradient-to-r from-green-500 to-emerald-600',
          bgHover: 'hover:from-green-600 hover:to-emerald-700',
          border: 'border-green-300',
          text: 'text-green-700 dark:text-green-300'
        };
      case 'school':
        return {
          gradient: 'from-purple-500 to-violet-600',
          bg: 'bg-gradient-to-r from-purple-500 to-violet-600',
          bgHover: 'hover:from-purple-600 hover:to-violet-700',
          border: 'border-purple-300',
          text: 'text-purple-700 dark:text-purple-300'
        };
      case 'demo':
        return {
          gradient: 'from-gray-400 to-gray-600',
          bg: 'bg-gradient-to-r from-gray-400 to-gray-600',
          bgHover: 'hover:from-gray-500 hover:to-gray-700',
          border: 'border-gray-300',
          text: 'text-gray-700 dark:text-gray-300'
        };
      default:
        return {
          gradient: 'from-gray-400 to-gray-600',
          bg: 'bg-gradient-to-r from-gray-400 to-gray-600',
          bgHover: 'hover:from-gray-500 hover:to-gray-700',
          border: 'border-gray-300',
          text: 'text-gray-700 dark:text-gray-300'
        };
    }
  };
  
  // Render current subscription card
  const renderCurrentSubscription = () => {
    if (loading) {
      return (
        <div className="animate-pulse p-6 bg-white dark:bg-gray-800 rounded-lg shadow-md">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-4"></div>
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-2"></div>
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-2/3 mb-2"></div>
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-4"></div>
          <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded w-full"></div>
        </div>
      );
    }
    
    if (error) {
      return (
        <div className="p-6 bg-white dark:bg-gray-800 rounded-lg shadow-md border-l-4 border-red-500">
          <h3 className="text-lg font-medium text-red-600 dark:text-red-400">{t.error}</h3>
          <p className="text-gray-600 dark:text-gray-400">{error}</p>
        </div>
      );
    }
    
    const colors = subscription?.has_subscription 
      ? getSubscriptionColor(subscription.subscription_type)
      : getSubscriptionColor('default');
      
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
          <div className={`h-2 bg-gradient-to-r ${colors.gradient}`}></div>
          <div className="p-6">
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              {t.currentSubscription}
            </h3>
            
            {subscription?.has_subscription ? (
              <>
                <div className="mb-6">
                  <div className="flex items-center mb-4">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${colors.bg} text-white`}>
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                      </svg>
                    </div>
                    <div className="ml-4">
                      <span className="capitalize text-2xl font-bold text-gray-900 dark:text-white">
                        {subscription.subscription_type}
                      </span>
                      {subscription.days_left > 0 && (
                        <span className="ml-2 px-3 py-1 bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 text-sm rounded-full">
                          {subscription.days_left} {t.days}
                        </span>
                      )}
                    </div>
                  </div>
                
                  <div className="mt-6 bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                    <div className="flex items-center mb-2">
                      <svg className="h-5 w-5 text-primary-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <span className="font-medium text-gray-700 dark:text-gray-300">{t.expiresAt}:</span>
                      <span className="ml-2 text-gray-900 dark:text-gray-100">
                        {new Date(subscription.expires_at).toLocaleDateString()}
                      </span>
                    </div>
                  
                    <div className="flex items-center">
                      <svg className="h-5 w-5 text-primary-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span className="font-medium text-gray-700 dark:text-gray-300">{t.daysLeft}:</span>
                      <span className="ml-2 text-gray-900 dark:text-gray-100">
                        {subscription.days_left} {t.days}
                      </span>
                    </div>
                  </div>
                </div>
                
                <button 
                  onClick={() => {
                    setActiveTab('buy');
                    setSelectedSubscriptionType(subscription.subscription_type);
                  }} 
                  className={`w-full ${colors.bg} ${colors.bgHover} text-white py-3 px-4 rounded-lg shadow-sm hover:shadow-md transition-all font-medium flex items-center justify-center`}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  {t.extendSubscription}
                </button>
              </>
            ) : (
              <>
                <div className="mb-6 text-center">
                  <div className="w-24 h-24 mx-auto mb-4 flex items-center justify-center bg-gray-100 dark:bg-gray-700 rounded-full">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 text-gray-400 dark:text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                    </svg>
                  </div>
                  <h4 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-2">{t.noActiveSubscription}</h4>
                  <p className="text-gray-500 dark:text-gray-400 mb-6">
                    {t.subscriptionBenefits}
                  </p>
                </div>
                
                <button 
                  onClick={() => setActiveTab('buy')} 
                  className="w-full bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-600 hover:to-primary-700 text-white py-3 px-4 rounded-lg shadow-sm hover:shadow-md transition-all font-medium flex items-center justify-center"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  {t.getSubscription}
                </button>
              </>
            )}
          </div>
        </div>
        
        {/* Subscription benefits */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
          <div className="h-2 bg-gradient-to-r from-purple-400 to-indigo-600"></div>
          <div className="p-6">
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              {t.benefitsTitle || "Преимущества подписки"}
            </h3>
            
            <ul className="space-y-3">
              <li className="flex items-start">
                <div className="flex-shrink-0 h-6 w-6 rounded-full bg-green-100 dark:bg-green-900/30 text-green-500 dark:text-green-400 flex items-center justify-center">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                </div>
                <p className="ml-3 text-base text-gray-700 dark:text-gray-300">
                  {t.benefitFullAccess || "Полный доступ ко всем тестам и категориям"}
                </p>
              </li>
              <li className="flex items-start">
                <div className="flex-shrink-0 h-6 w-6 rounded-full bg-green-100 dark:bg-green-900/30 text-green-500 dark:text-green-400 flex items-center justify-center">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                </div>
                <p className="ml-3 text-base text-gray-700 dark:text-gray-300">
                  {t.benefitStatistics || "Подробная аналитика и статистика результатов"}
                </p>
              </li>
              <li className="flex items-start">
                <div className="flex-shrink-0 h-6 w-6 rounded-full bg-green-100 dark:bg-green-900/30 text-green-500 dark:text-green-400 flex items-center justify-center">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                </div>
                <p className="ml-3 text-base text-gray-700 dark:text-gray-300">
                  {t.benefitWithoutAds || "Тесты без рекламы и ограничений"}
                </p>
              </li>
              <li className="flex items-start">
                <div className="flex-shrink-0 h-6 w-6 rounded-full bg-green-100 dark:bg-green-900/30 text-green-500 dark:text-green-400 flex items-center justify-center">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                </div>
                <p className="ml-3 text-base text-gray-700 dark:text-gray-300">
                  {t.benefitMultiplayer || "Мультиплеер режим с друзьями"}
                </p>
              </li>
              <li className="flex items-start">
                <div className="flex-shrink-0 h-6 w-6 rounded-full bg-green-100 dark:bg-green-900/30 text-green-500 dark:text-green-400 flex items-center justify-center">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                </div>
                <p className="ml-3 text-base text-gray-700 dark:text-gray-300">
                  {t.benefitPriority || "Приоритетная поддержка"}
                </p>
              </li>
            </ul>
          </div>
        </div>
      </div>
    );
  };
  
  // Render subscription plans
  const renderSubscriptionPlans = () => {
    const plans = [
      { 
        id: 'economy', 
        title: t.economyTitle || "Эконом", 
        price: 1990, 
        features: [
          t.economyFeature1 || "Доступ к категориям A, A1, B", 
          t.economyFeature2 || "Полная база вопросов", 
          t.economyFeature3 || "Доступ к базовой статистике"
        ] 
      },
      { 
        id: 'Vip', 
        title: t.vipTitle || "VIP", 
        price: 3990, 
        featured: true, 
        features: [
          t.vipFeature1 || "Доступ ко всем категориям", 
          t.vipFeature2 || "Создание реферальной ссылки", 
          t.vipFeature3 || "Доступ к полной статистике", 
          t.vipFeature4 || "Создание лобби для мультиплеера"
        ] 
      },
      { 
        id: 'Royal', 
        title: t.royalTitle || "Royal", 
        price: 6990, 
        features: [
          t.royalFeature1 || "Все функции VIP тарифа", 
          t.royalFeature2 || "Дарение тестов и групповые коды", 
          t.royalFeature3 || "Скидка 15% в автошколу", 
          t.royalFeature4 || "Приоритетная поддержка", 
          t.royalFeature5 || "Ранний доступ к новым функциям"
        ] 
      }
    ];
    
    const durations = [
      { value: 1, label: t.month1 || "1 месяц" },
      { value: 3, label: t.months3 || "3 месяца", discount: '10%' },
      { value: 6, label: t.months6 || "6 месяцев", discount: '15%' },
      { value: 12, label: t.year1 || "1 год", discount: '25%' }
    ];
    
    return (
      <div className="space-y-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
          <div className="h-2 bg-gradient-to-r from-primary-400 to-primary-600"></div>
          <div className="p-6">
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              {isForGift ? (t.buySubscriptionGift || "Подарить подписку") : (t.buySubscription || "Купить подписку")}
            </h3>
            
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t.subscriptionType || "Тип подписки"}
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {plans.map((plan) => {
                  const colors = getSubscriptionColor(plan.id);
                  const isSelected = selectedSubscriptionType === plan.id;
                  
                  return (
                    <div 
                      key={plan.id}
                      onClick={() => setSelectedSubscriptionType(plan.id)}
                      className={`cursor-pointer p-4 rounded-lg border-2 transition-all ${
                        isSelected 
                          ? `${colors.border} shadow-md` 
                          : 'border-gray-200 dark:border-gray-700'
                      }`}
                    >
                      <div className="flex items-center mb-2">
                        <div className={`w-5 h-5 rounded-full border-2 mr-2 flex items-center justify-center ${
                          isSelected 
                            ? `${colors.border} border-2` 
                            : 'border-gray-300 dark:border-gray-600'
                        }`}>
                          {isSelected && <div className={`w-3 h-3 rounded-full ${colors.bg}`}></div>}
                        </div>
                        <span className={`font-medium ${isSelected ? colors.text : 'text-gray-700 dark:text-gray-300'}`}>
                          {plan.title}
                        </span>
                        {plan.featured && (
                          <span className="ml-2 px-2 py-0.5 bg-primary-100 dark:bg-primary-900 text-primary-800 dark:text-primary-200 text-xs rounded-full">
                            {t.popular || "Популярный"}
                          </span>
                        )}
                      </div>
                      <div className="ml-7">
                        <div className="text-lg font-bold text-gray-900 dark:text-white mb-1">
                          {formatMoney(plan.price)} <span className="text-xs text-gray-500 dark:text-gray-400">/ {t.month || "месяц"}</span>
                        </div>
                        <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                          {plan.features.map((feature, index) => (
                            <li key={index} className="flex items-start">
                              <svg className="h-4 w-4 text-green-500 mt-0.5 mr-1.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                              </svg>
                              <span>{feature}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t.duration || "Длительность"}
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {durations.map((duration) => {
                  const isSelected = selectedDuration === duration.value;
                  
                  return (
                    <div 
                      key={duration.value}
                      onClick={() => setSelectedDuration(duration.value)}
                      className={`cursor-pointer p-3 rounded-lg border-2 transition-all text-center ${
                        isSelected 
                          ? 'border-primary-400 dark:border-primary-500 bg-primary-50 dark:bg-primary-900/20' 
                          : 'border-gray-200 dark:border-gray-700'
                      }`}
                    >
                      <div className="font-medium text-gray-900 dark:text-white">
                        {duration.label}
                      </div>
                      {duration.discount && (
                        <div className="text-xs text-green-600 dark:text-green-400 mt-1">
                          {t.save || "Скидка"} {duration.discount}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
            
            {isForGift && (
              <div className="mb-6">
                <div className="p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                  <h4 className="font-medium text-amber-800 dark:text-amber-300 mb-2">{t.giftInformation || "Информация о подарке"}</h4>
                  <p className="text-sm text-amber-700 dark:text-amber-400">
                    {t.giftInformationText || "Вы можете подарить подписку любому пользователю, зная его ИИН. Подписка будет активирована автоматически после оплаты."}
                  </p>
                </div>
              </div>
            )}
            
            <div className="flex flex-col sm:flex-row sm:justify-between items-center border-t border-gray-200 dark:border-gray-700 pt-4">
              <div className="mb-4 sm:mb-0">
                <div className="text-sm text-gray-600 dark:text-gray-400">{t.totalPrice || "Итоговая цена"}</div>
                <div className="text-2xl font-bold text-gray-900 dark:text-white">
                  {formatMoney(getSubscriptionPrice(selectedSubscriptionType, selectedDuration))}
                </div>
              </div>
              
              <div className="flex flex-col sm:flex-row gap-3">
                {!isForGift && (
                  <button
                    onClick={() => setIsForGift(true)}
                    className="px-6 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                  >
                    {t.buyAsGift || "Купить как подарок"}
                  </button>
                )}
                
                <button
                  onClick={isForGift ? handlePurchaseGift : handlePurchaseSubscription}
                  className="px-6 py-2 bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-600 hover:to-primary-700 text-white rounded-lg font-medium shadow-sm hover:shadow transition-all"
                >
                  {isForGift ? (t.purchaseGift || "Купить подарок") : (t.purchaseForSelf || "Купить для себя")}
                </button>
              </div>
            </div>
          </div>
        </div>
        
        {isForGift && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
            <div className="h-2 bg-gradient-to-r from-blue-400 to-indigo-500"></div>
            <div className="p-6">
              <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                {t.giftByIIN || "Подарить по ИИН"}
              </h3>
              
              <form onSubmit={handleGiftByIIN}>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    {t.recipientIIN || "ИИН получателя"}
                  </label>
                  <input
                    type="text"
                    value={iinValue}
                    onChange={(e) => setIinValue(e.target.value)}
                    placeholder="000000000000"
                    className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 dark:bg-gray-700 dark:text-white"
                    maxLength={12}
                    pattern="\d{12}"
                    required
                  />
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    {t.iinDescription || "Введите 12-значный ИИН получателя подарка"}
                  </p>
                </div>
                
                <button
                  type="submit"
                  className="w-full py-2 bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white rounded-lg font-medium shadow-sm hover:shadow transition-all"
                >
                  {t.sendGift || "Отправить подарок"}
                </button>
              </form>
            </div>
          </div>
        )}
      </div>
    );
  };
  
  // Render balance and promo code forms
  const renderBalanceAndPromo = () => {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
          <div className="h-2 bg-gradient-to-r from-emerald-400 to-green-500"></div>
          <div className="p-6">
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              {t.topUpBalance || "Пополнить баланс"}
            </h3>
            
            <div className="mb-4">
              <div className="flex items-center justify-between">
                <span className="text-gray-700 dark:text-gray-300">{t.currentBalance || "Текущий баланс"}:</span>
                <span className="text-lg font-bold text-gray-900 dark:text-white">{formatMoney(profileData?.money)}</span>
              </div>
            </div>
            
            <form onSubmit={handleTopUp}>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t.amount || "Сумма"} (KZT)
                </label>
                <input
                  type="number"
                  min="100"
                  step="100"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="1000"
                  className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 dark:bg-gray-700 dark:text-white"
                  required
                />
              </div>
              
              <div className="flex flex-wrap gap-2 mb-4">
                {[1000, 2000, 5000, 10000].map((value) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setAmount(value)}
                    className="px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-full text-sm hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                  >
                    +{formatMoney(value)}
                  </button>
                ))}
              </div>
              
              <button
                type="submit"
                className="w-full py-2 bg-gradient-to-r from-emerald-500 to-green-500 hover:from-emerald-600 hover:to-green-600 text-white rounded-lg font-medium shadow-sm hover:shadow transition-all"
              >
                {t.topUp || "Пополнить"}
              </button>
            </form>
          </div>
        </div>
        
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
          <div className="h-2 bg-gradient-to-r from-purple-400 to-indigo-500"></div>
          <div className="p-6">
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              {t.activatePromoCode || "Активировать промокод"}
            </h3>
            
            <form onSubmit={handleActivatePromo}>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t.promoCode || "Промокод"}
                </label>
                <input
                  type="text"
                  value={promoCode}
                  onChange={(e) => setPromoCode(e.target.value)}
                  placeholder="XXXX-XXXX-XXXX"
                  className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 dark:bg-gray-700 dark:text-white"
                  required
                />
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  {t.promoCodeDescription || "Введите промокод для активации подписки или получения бонуса"}
                </p>
              </div>
              
              <button
                type="submit"
                className="w-full py-2 bg-gradient-to-r from-purple-500 to-indigo-600 hover:from-purple-600 hover:to-indigo-700 text-white rounded-lg font-medium shadow-sm hover:shadow transition-all"
              >
                {t.activate || "Активировать"}
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  };
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
        <div className="h-2 bg-gradient-to-r from-primary-600 to-primary-400"></div>
        <div className="p-6">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {t.subscriptionManagement || "Управление подпиской"}
          </h1>
          <p className="text-gray-600 dark:text-gray-300">
            {t.subscriptionDescription || "Здесь вы можете управлять вашей подпиской, пополнить баланс или активировать промокод"}
          </p>
        </div>
      </div>
      
      {/* Tabs */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
        <div className="flex border-b border-gray-200 dark:border-gray-700">
          <button
            onClick={() => setActiveTab('subscription')}
            className={`flex-1 py-4 px-6 text-center font-medium ${
              activeTab === 'subscription'
                ? 'text-primary-600 dark:text-primary-400 border-b-2 border-primary-500'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
            }`}
          >
            {t.mySubscription || "Моя подписка"}
          </button>
          <button
            onClick={() => { setActiveTab('buy'); setIsForGift(false); }}
            className={`flex-1 py-4 px-6 text-center font-medium ${
              activeTab === 'buy'
                ? 'text-primary-600 dark:text-primary-400 border-b-2 border-primary-500'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
            }`}
          >
            {t.buySubscription || "Купить подписку"}
          </button>
          <button
            onClick={() => setActiveTab('balance')}
            className={`flex-1 py-4 px-6 text-center font-medium ${
              activeTab === 'balance'
                ? 'text-primary-600 dark:text-primary-400 border-b-2 border-primary-500'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
            }`}
          >
            {t.balanceAndPromo || "Баланс и промокоды"}
          </button>
        </div>
      </div>
      
      {/* Tab Content */}
      {activeTab === 'subscription' && renderCurrentSubscription()}
      {activeTab === 'buy' && renderSubscriptionPlans()}
      {activeTab === 'balance' && renderBalanceAndPromo()}
    </div>
  );
};

export default SubscriptionPage; 