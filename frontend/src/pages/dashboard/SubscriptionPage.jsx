import React, { useState, useEffect } from 'react';
import { useLanguage } from '../../contexts/LanguageContext';
import { translations } from '../../translations/translations';
import { toast } from 'react-toastify';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import 'react-toastify/dist/ReactToastify.css';

const SubscriptionPage = () => {
  const { language } = useLanguage();
  const tLang = translations[language];
  const navigate = useNavigate();
  
  // State for subscription data
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(false);
  const [purchaseLoading, setPurchaseLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('subscription');
  const [selectedSubscriptionType, setSelectedSubscriptionType] = useState('economy');
  const [selectedDuration, setSelectedDuration] = useState(1);
  const [isGiftMode, setIsGiftMode] = useState(false);
  const [giftOption, setGiftOption] = useState('iin');
  const [giftIIN, setGiftIIN] = useState('');
  const [showGiftOptions, setShowGiftOptions] = useState(false);
  const [giftType, setGiftType] = useState(null);
  const [topUpAmount, setTopUpAmount] = useState('');
  const [customAmount, setCustomAmount] = useState(false);
  const [balance, setBalance] = useState(null);
  const [promoCode, setPromoCode] = useState('');
  
  // Fetch current subscription data
  useEffect(() => {
    const initData = async () => {
      await fetchSubscription();
      await fetchUserProfile();
    };
    initData();
  }, []);
  
  // Fetch subscription data from the server
  const fetchSubscription = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/users/my/subscription', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        // Handle new API response format with `data` property
        if (data.data && data.status === "ok") {
          const subData = data.data;
          if (subData.has_subscription) {
            setSubscription({
              subscription_type: subData.subscription_type,
              expiry_date: subData.expires_at,
              created_at: new Date().toISOString(),
              active: true,
              auto_renewal: false,
              days_left: subData.days_left,
              duration_days: subData.duration_days
            });
          } else {
            setSubscription(null);
          }
          // (balance comes from user profile, so skip here)
        } else {
          // Legacy API response format
          setSubscription({
            ...data.subscription,
            duration_days: data.subscription.duration_days || 30
          });
          // (balance comes from user profile, so skip here)
        }
      }
    } catch (error) {
      console.error('Error fetching subscription:', error);
    } finally {
      setLoading(false);
    }
  };
  
  // Fetch user profile to get wallet balance
  const fetchUserProfile = async () => {
    try {
      const response = await fetch('/api/users/me', { credentials: 'include' });
      if (response.ok) {
        const result = await response.json();
        if (result.data && typeof result.data.money === 'number') {
          setBalance(result.data.money);
        }
      }
    } catch (err) {
      console.error('Error fetching user profile balance:', err);
    }
  };
  
  // Format money values
  const formatMoney = (amount) => {
    return new Intl.NumberFormat('ru-KZ', {
      style: 'currency',
      currency: 'KZT',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount || 0);
  };
  
  // Get subscription price based on type and duration
  const getSubscriptionPrice = (type, months = selectedDuration) => {
    const basePrice = {
      'economy': 2000,  // Новая цена (было 5000)
      'vip': 4000,      // Новая цена (было 10000) 
      'royal': 6000     // Новая цена (было 15000)
    }[type] || 2000;
    
    // Apply discount based on selected duration
    let discount = 0;
    if (months === 3) discount = 0.05; // 5% discount for 3 months
    if (months === 6) discount = 0.10; // 10% discount for 6 months
    
    return basePrice * months * (1 - discount);
  };
  
  // Get old price for strikethrough
  const getOldPrice = (type, months = selectedDuration) => {
    const oldBasePrice = {
      'economy': 5000,
      'vip': 10000,
      'royal': 15000
    }[type] || 5000;
    
    let discount = 0;
    if (months === 3) discount = 0.05;
    if (months === 6) discount = 0.10;
    
    return oldBasePrice * months * (1 - discount);
  };
  
  // Handle subscription purchase
  const handlePurchaseSubscription = async (event) => {
    event.preventDefault();
    
    try {
      setPurchaseLoading(true);
      
      // Call our new API endpoint to purchase subscription
      const response = await axios.post('/api/users/purchase-subscription', {
        subscription_type: selectedSubscriptionType,
        duration_days: selectedDuration * 30, // Convert months to days
        use_balance: true
      }, {
        withCredentials: true,
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (response.data.status === "ok") {
        toast.success(tLang.purchaseSuccess || "Subscription purchased successfully!", {
          autoClose: 5000
        });
        
        // Update balance from response
        if (response.data.data && typeof response.data.data.balance_after === 'number') {
          setBalance(response.data.data.balance_after);
        } else {
          // Fallback to fetching profile
          await fetchUserProfile();
        }
        
        // Refresh subscription details
        await fetchSubscription();
      } else {
        throw new Error(response.data.message || "Failed to purchase subscription");
      }
    } catch (error) {
      console.error("Error purchasing subscription:", error);
      
      // Extract error message from different possible response formats
      let errorMessage = tLang.errorPurchasingSubscription || "Error purchasing subscription";
      
      if (error.response && error.response.data) {
        // Server returned an error response
        const errorData = error.response.data;
        if (errorData.message) {
          errorMessage = errorData.message;
        } else if (errorData.details && errorData.details.message) {
          errorMessage = errorData.details.message;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      toast.error(errorMessage);
    } finally {
      setPurchaseLoading(false);
    }
  };
  
  // Handle gift purchase
  const handlePurchaseGift = async (event) => {
    event.preventDefault();
    
    // Validate IIN if gift by IIN is selected
    if (giftOption === 'iin' && (!giftIIN || giftIIN.length !== 12)) {
      toast.error(tLang.invalidIIN || "Please enter a valid 12-digit IIN");
      return;
    }
    
    // Calculate price based on subscription type and duration
    const price = getSubscriptionPrice(selectedSubscriptionType, selectedDuration);
    
    // Check if user has enough balance
    if (balance < price) {
      toast.error(tLang.notEnoughBalance || "У вас недостаточно средств на балансе для совершения этой покупки");
      return;
    }
    
    try {
      setPurchaseLoading(true);
      
      if (giftOption === 'iin') {
        // Make API call to purchase gift subscription by IIN
        const response = await axios.post('/api/users/purchase-gift-subscription', {
          gift_iin: giftIIN,
          subscription_type: selectedSubscriptionType,
          duration_days: selectedDuration * 30, // Convert months to days
          use_balance: true
        }, {
          withCredentials: true,
          headers: {
            'Content-Type': 'application/json'
          }
        });
        
        if (response.data.status === "ok") {
          toast.success(tLang.giftPurchaseSuccess || "Gift purchased successfully!");
          
          // Update balance from response
          if (response.data.data && typeof response.data.data.balance_after === 'number') {
            setBalance(response.data.data.balance_after);
          } else {
            await fetchUserProfile();
          }
          
          // Reset form
          setGiftIIN('');
        } else {
          throw new Error(response.data.message || "Failed to purchase gift");
        }
      } else if (giftOption === 'promo') {
        // Purchase as a promo code instead
        const response = await axios.post('/api/users/generate-promo-code', {
          subscription_type: selectedSubscriptionType,
          duration_days: selectedDuration * 30 // Convert months to days
        }, {
          withCredentials: true,
          headers: {
            'Content-Type': 'application/json'
          }
        });
        
        if (response.data.status === "ok") {
          const promoCode = response.data.data?.promo_code;
          toast.success(
            (promoCode ? `${tLang.yourPromoCode || "Ваш промокод"}: ${promoCode}. ` : '') +
            (response.data.message || 
            tLang.promoCodeCreated || 
            "Промокод успешно создан. Вы можете поделиться им с кем угодно."),
            {
              autoClose: 8000,
              position: "top-right",
              hideProgressBar: false,
              closeOnClick: true,
              pauseOnHover: true,
              draggable: true
            }
          );
          
          // Update balance from response
          if (response.data.data && typeof response.data.data.balance_after === 'number') {
            setBalance(response.data.data.balance_after);
          } else {
            await fetchUserProfile();
          }
        } else {
          throw new Error(response.data.message || "Failed to create promo code");
        }
      }
    } catch (error) {
      console.error("Error purchasing gift:", error);
      
      // Extract error message from different possible response formats
      let errorMessage = tLang.errorPurchasingGift || "Error purchasing gift";
      
      if (error.response && error.response.data) {
        // Server returned an error response
        const errorData = error.response.data;
        if (errorData.message) {
          errorMessage = errorData.message;
        } else if (errorData.details && errorData.details.message) {
          errorMessage = errorData.details.message;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      toast.error(errorMessage);
    } finally {
      setPurchaseLoading(false);
    }
  };
  
  // Handle balance top-up
  const handleTopUp = async (event) => {
    event.preventDefault();
    
    try {
      // Get the selected amount from the form
      const formElement = event.target;
      const amount = formElement.querySelector('#amount')?.value || topUpAmount;
      
      if (!amount || isNaN(amount) || parseInt(amount) < 500) {
        toast.error(tLang.minAmountError || "Минимальная сумма для пополнения: 500 ₸");
        return;
      }
      
      // Navigate to the payment page with top-up details
      navigate('/dashboard/payment', {
        state: {
          paymentDetails: {
            isTopUp: true,
            price: parseInt(amount),
            date: new Date().toLocaleDateString(),
            orderId: `ORD-${Math.floor(Math.random() * 100000)}`
          }
        }
      });
      
      // Note: The success toast will be shown after successful payment in the payment page
      // We're just navigating away here, so we don't need to show a toast yet
      
    } catch (error) {
      console.error("Error processing top up request:", error);
      
      // Extract error message from different possible response formats
      let errorMessage = tLang.errorProcessingPayment || "Error processing payment";
      
      if (error.response && error.response.data) {
        // Server returned an error response
        const errorData = error.response.data;
        if (errorData.message) {
          errorMessage = errorData.message;
        } else if (errorData.details && errorData.details.message) {
          errorMessage = errorData.details.message;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      toast.error(errorMessage);
    }
  };
  
  // Handle promo code activation
  const handleActivatePromo = async (event) => {
    event.preventDefault();
    
    try {
      // Get promo code from the form
      const formElement = event.target;
      const promoCode = formElement.querySelector('#promoCode')?.value;
      
      if (!promoCode || promoCode.trim() === '') {
        toast.error(tLang.promoCodeRequired || "Пожалуйста, введите промокод");
        return;
      }
      
      setPurchaseLoading(true);
      
      // Make API request to activate promo code using our new endpoint
      const response = await axios.post('/api/users/activate-promo-code', { 
        promo_code: promoCode.trim() 
      }, {
        withCredentials: true,
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (response.data.status === "ok") {
        toast.success(tLang.promoActivatedSuccess || "Promo code activated successfully!");
        
        // Clear input field
        formElement.querySelector('#promoCode').value = '';
        
        // Refresh subscription data
        await fetchSubscription();
      } else {
        throw new Error(response.data.message || "Failed to activate promo code");
      }
    } catch (error) {
      console.error("Error activating promo code:", error);
      
      // Extract error message from different possible response formats
      let errorMessage = tLang.errorActivatingPromo || "Error activating promo code";
      
      if (error.response && error.response.data) {
        // Server returned an error response
        const errorData = error.response.data;
        if (errorData.message) {
          errorMessage = errorData.message;
        } else if (errorData.details && errorData.details.message) {
          errorMessage = errorData.details.message;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      toast.error(errorMessage);
    } finally {
      setPurchaseLoading(false);
    }
  };
  
  // Handle gift by IIN
  const handleGiftByIIN = async (event) => {
    event.preventDefault();
    
    if (!giftIIN || giftIIN.length !== 12) {
      toast.error(tLang.invalidIIN || "Please enter a valid 12-digit IIN");
      return;
    }
    
    // Calculate price based on subscription type and duration
    const price = getSubscriptionPrice(selectedSubscriptionType, selectedDuration);
    
    // Check if user has enough balance
    if (balance < price) {
      toast.error(tLang.notEnoughBalance || "У вас недостаточно средств на балансе для совершения этой покупки");
      return;
    }
    
    try {
      setPurchaseLoading(true);
      
      // Call API to purchase gift subscription directly
      const response = await axios.post('/api/users/purchase-gift-subscription', {
        gift_iin: giftIIN,
        subscription_type: selectedSubscriptionType,
        duration_days: selectedDuration * 30, // Convert months to days
        use_balance: true
      }, {
        withCredentials: true,
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (response.data.status === "ok") {
        toast.success(tLang.giftSentSuccess || "Gift sent successfully!");
        
        // Update balance from response
        if (response.data.data && typeof response.data.data.balance_after === 'number') {
          setBalance(response.data.data.balance_after);
        } else {
          await fetchUserProfile();
        }
        
        // Reset gift IIN
        setGiftIIN('');
      } else {
        throw new Error(response.data.message || "Failed to send gift");
      }
    } catch (error) {
      console.error("Error sending gift:", error);
      
      // Extract error message from different possible response formats
      let errorMessage = tLang.errorSendingGift || "Error sending gift";
      
      if (error.response && error.response.data) {
        // Server returned an error response
        const errorData = error.response.data;
        if (errorData.message) {
          errorMessage = errorData.message;
        } else if (errorData.details && errorData.details.message) {
          errorMessage = errorData.details.message;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      toast.error(errorMessage);
    } finally {
      setPurchaseLoading(false);
    }
  };
  
  // Get subscription color based on type
  const getSubscriptionColor = (type) => {
    switch(type?.toLowerCase()) {
      case 'economy':
        return {
          background: 'bg-gradient-to-r from-blue-400 to-blue-600',
          border: 'border-blue-500',
          text: 'text-blue-500',
          button: 'bg-blue-500 hover:bg-blue-600'
        };
      case 'vip':
        return {
          background: 'bg-gradient-to-r from-purple-400 to-purple-600',
          border: 'border-purple-500',
          text: 'text-purple-500',
          button: 'bg-purple-500 hover:bg-purple-600'
        };
      case 'royal':
        return {
          background: 'bg-gradient-to-r from-amber-400 to-amber-600',
          border: 'border-amber-500',
          text: 'text-amber-500',
          button: 'bg-amber-500 hover:bg-amber-600'
        };
      case 'school':
        return {
          background: 'bg-gradient-to-r from-green-400 to-green-600',
          border: 'border-green-500',
          text: 'text-green-500',
          button: 'bg-green-500 hover:bg-green-600'
        };
      case 'demo':
        return {
          background: 'bg-gradient-to-r from-gray-400 to-gray-600',
          border: 'border-gray-500',
          text: 'text-gray-500',
          button: 'bg-gray-500 hover:bg-gray-600'
        };
      default:
        return {
          background: 'bg-gradient-to-r from-gray-400 to-gray-600',
          border: 'border-gray-500',
          text: 'text-gray-500',
          button: 'bg-gray-500 hover:bg-gray-600'
        };
    }
  };
  
  // Render subscription types grid
  const renderSubscriptionTypes = () => {
    return (
      <div className="mb-8">
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-3">
            {tLang.choosePlanSubtitle || "Выберите тариф"}
          </h2>
          <p className="text-lg text-gray-600 dark:text-gray-400">
            {tLang.specialPricesPromo || "Специальные цены! Экономьте до 60% на всех тарифах"}
          </p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {/* Economy Plan */}
          <div 
            className={`relative overflow-hidden rounded-3xl transition-all duration-300 border-3 cursor-pointer group ${
              selectedSubscriptionType === 'economy' 
                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/10 shadow-xl shadow-blue-100 dark:shadow-blue-900/20 scale-105' 
                : 'border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600 hover:scale-102'
            }`}
            onClick={() => setSelectedSubscriptionType('economy')}
          >
            {/* Popular Badge for VIP */}
            <div className="p-8 flex flex-col h-full min-h-[500px]">
              <div className="text-center mb-6">
                <div className={`inline-flex p-4 rounded-full mb-4 ${selectedSubscriptionType === 'economy' ? 'bg-blue-500' : 'bg-gray-200 dark:bg-gray-700'} text-white transition-colors`}>
                  <span className="text-2xl">🪙</span>
                </div>
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">{tLang.economyTitle || "Эконом"}</h3>
                <p className="text-gray-500 dark:text-gray-400">{tLang.basicPlan || "Базовый план"}</p>
              </div>
              
              {/* Pricing with old price crossed out */}
              <div className="text-center mb-8">
                <div className="mb-2">
                  <span className="text-sm text-gray-500 line-through">{formatMoney(getOldPrice('economy'))}</span>
                </div>
                <div className="flex items-baseline justify-center">
                  <span className="text-4xl font-extrabold text-gray-900 dark:text-white">{formatMoney(getSubscriptionPrice('economy'))}</span>
                  <span className="text-lg ml-2 text-gray-500 dark:text-gray-400">{tLang.perMonth || "/ мес"}</span>
                </div>
                <div className="mt-2">
                  <span className="inline-block bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 text-sm font-semibold px-3 py-1 rounded-full">
                    {tLang.savings || "Экономия"} {Math.round(((getOldPrice('economy') - getSubscriptionPrice('economy')) / getOldPrice('economy')) * 100)}%
                  </span>
                </div>
              </div>
              
              <ul className="space-y-4 mb-8 flex-grow">
                <li className="flex items-start">
                  <svg className="h-6 w-6 text-blue-500 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300 font-medium">{tLang.fullTestAccess || "Доступ ко всем тестам"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-6 w-6 text-blue-500 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300 font-medium">{tLang.basicStatistics || "Базовая статистика"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-6 w-6 text-blue-500 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300 font-medium">{tLang.emailSupport || "Email поддержка"}</span>
                </li>
              </ul>
              
              <button
                type="button"
                className={`w-full py-4 px-6 rounded-xl text-center font-bold text-lg transition-all duration-200 ${
                  selectedSubscriptionType === 'economy'
                    ? 'bg-blue-500 hover:bg-blue-600 text-white shadow-lg shadow-blue-200 dark:shadow-blue-900/20'
                    : 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200'
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedSubscriptionType('economy');
                }}
              >
                {selectedSubscriptionType === 'economy' ? (tLang.selected || '✓ Выбрано') : (tLang.selectPlan || 'Выбрать тариф')}
              </button>
            </div>
          </div>

          {/* VIP Plan */}
          <div 
            className={`relative overflow-hidden rounded-3xl transition-all duration-300 border-3 cursor-pointer group ${
              selectedSubscriptionType === 'vip' 
                ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/10 shadow-xl shadow-purple-100 dark:shadow-purple-900/20 scale-105' 
                : 'border-gray-200 dark:border-gray-700 hover:border-purple-300 dark:hover:border-purple-600 hover:scale-102'
            }`}
            onClick={() => setSelectedSubscriptionType('vip')}
          >
            {/* Popular Badge */}
            <div className="absolute top-6 right-6 z-10">
              <span className="bg-gradient-to-r from-purple-500 to-pink-500 text-white text-sm px-4 py-2 rounded-full font-bold shadow-lg">
                🔥 {tLang.popular || "Популярный"}
              </span>
            </div>
            
            <div className="p-8 flex flex-col h-full min-h-[500px]">
              <div className="text-center mb-6">
                <div className={`inline-flex p-4 rounded-full mb-4 ${selectedSubscriptionType === 'vip' ? 'bg-purple-500' : 'bg-gray-200 dark:bg-gray-700'} text-white transition-colors`}>
                  <span className="text-2xl">⭐</span>
                </div>
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">{tLang.vipTitle || "VIP"}</h3>
                <p className="text-gray-500 dark:text-gray-400">{tLang.advancedPlan || "Продвинутый план"}</p>
              </div>
              
              {/* Pricing with old price crossed out */}
              <div className="text-center mb-8">
                <div className="mb-2">
                  <span className="text-sm text-gray-500 line-through">{formatMoney(getOldPrice('vip'))}</span>
                </div>
                <div className="flex items-baseline justify-center">
                  <span className="text-4xl font-extrabold text-gray-900 dark:text-white">{formatMoney(getSubscriptionPrice('vip'))}</span>
                  <span className="text-lg ml-2 text-gray-500 dark:text-gray-400">{tLang.perMonth || "/ мес"}</span>
                </div>
                <div className="mt-2">
                  <span className="inline-block bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 text-sm font-semibold px-3 py-1 rounded-full">
                    {tLang.savings || "Экономия"} {Math.round(((getOldPrice('vip') - getSubscriptionPrice('vip')) / getOldPrice('vip')) * 100)}%
                  </span>
                </div>
              </div>
              
              <ul className="space-y-4 mb-8 flex-grow">
                <li className="flex items-start">
                  <svg className="h-6 w-6 text-purple-500 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300 font-medium">{tLang.allEconomyFeatures || "Все функции Эконом"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-6 w-6 text-purple-500 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300 font-medium">{tLang.detailedStats || "Детальная статистика"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-6 w-6 text-purple-500 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300 font-medium">{tLang.createReferrals || "Реферальные ссылки"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-6 w-6 text-purple-500 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300 font-medium">{tLang.prioritySupport || "Приоритетная поддержка"}</span>
                </li>
              </ul>
              
              <button
                type="button"
                className={`w-full py-4 px-6 rounded-xl text-center font-bold text-lg transition-all duration-200 ${
                  selectedSubscriptionType === 'vip'
                    ? 'bg-purple-500 hover:bg-purple-600 text-white shadow-lg shadow-purple-200 dark:shadow-purple-900/20'
                    : 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200'
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedSubscriptionType('vip');
                }}
              >
                {selectedSubscriptionType === 'vip' ? (tLang.selected || '✓ Выбрано') : (tLang.selectPlan || 'Выбрать тариф')}
              </button>
            </div>
          </div>

          {/* Royal Plan */}
          <div 
            className={`relative overflow-hidden rounded-3xl transition-all duration-300 border-3 cursor-pointer group ${
              selectedSubscriptionType === 'royal' 
                ? 'border-amber-500 bg-amber-50 dark:bg-amber-900/10 shadow-xl shadow-amber-100 dark:shadow-amber-900/20 scale-105' 
                : 'border-gray-200 dark:border-gray-700 hover:border-amber-300 dark:hover:border-amber-600 hover:scale-102'
            }`}
            onClick={() => setSelectedSubscriptionType('royal')}
          >
            <div className="p-8 flex flex-col h-full min-h-[500px]">
              <div className="text-center mb-6">
                <div className={`inline-flex p-4 rounded-full mb-4 ${selectedSubscriptionType === 'royal' ? 'bg-amber-500' : 'bg-gray-200 dark:bg-gray-700'} text-white transition-colors`}>
                  <span className="text-2xl">👑</span>
                </div>
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">{tLang.royalTitle || "Роял"}</h3>
                <p className="text-gray-500 dark:text-gray-400">{tLang.premiumPlan || "Премиум план"}</p>
              </div>
              
              {/* Pricing with old price crossed out */}
              <div className="text-center mb-8">
                <div className="mb-2">
                  <span className="text-sm text-gray-500 line-through">{formatMoney(getOldPrice('royal'))}</span>
                </div>
                <div className="flex items-baseline justify-center">
                  <span className="text-4xl font-extrabold text-gray-900 dark:text-white">{formatMoney(getSubscriptionPrice('royal'))}</span>
                  <span className="text-lg ml-2 text-gray-500 dark:text-gray-400">{tLang.perMonth || "/ мес"}</span>
                </div>
                <div className="mt-2">
                  <span className="inline-block bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 text-sm font-semibold px-3 py-1 rounded-full">
                    {tLang.savings || "Экономия"} {Math.round(((getOldPrice('royal') - getSubscriptionPrice('royal')) / getOldPrice('royal')) * 100)}%
                  </span>
                </div>
              </div>
              
              <ul className="space-y-4 mb-8 flex-grow">
                <li className="flex items-start">
                  <svg className="h-6 w-6 text-amber-500 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300 font-medium">{tLang.allVIPFeatures || "Все функции VIP"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-6 w-6 text-amber-500 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300 font-medium">{tLang.exclusiveContent || "Эксклюзивный контент"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-6 w-6 text-amber-500 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300 font-medium">{tLang.premiumSupport || "24/7 поддержка"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-6 w-6 text-amber-500 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300 font-medium">{tLang.specialDiscounts || "Скидки на доп. услуги"}</span>
                </li>
              </ul>
              
              <button
                type="button"
                className={`w-full py-4 px-6 rounded-xl text-center font-bold text-lg transition-all duration-200 ${
                  selectedSubscriptionType === 'royal'
                    ? 'bg-amber-500 hover:bg-amber-600 text-white shadow-lg shadow-amber-200 dark:shadow-amber-900/20'
                    : 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200'
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedSubscriptionType('royal');
                }}
              >
                {selectedSubscriptionType === 'royal' ? (tLang.selected || '✓ Выбрано') : (tLang.selectPlan || 'Выбрать тариф')}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Render current subscription with improved design
  const renderCurrentSubscription = () => {
    if (!subscription) {
      return (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 text-center">
          <div className="flex justify-center mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">{tLang.noActiveSubscription || "You don't have an active subscription"}</h3>
          <p className="text-gray-600 dark:text-gray-400 mb-4">{tLang.subscriptionBenefits || "Choose a suitable plan and start using all the features"}</p>
          <button
            type="button"
            onClick={() => setActiveTab('buy')}
            className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-medium"
          >
            {tLang.getSubscription || "Get Subscription"}
          </button>
        </div>
      );
    }
    
    // Calculate days left
    const expiryDate = new Date(subscription.expiry_date);
    const today = new Date();
    const daysLeft = Math.ceil((expiryDate - today) / (1000 * 60 * 60 * 24));
    
    // Calculate percentage of time left
    const totalDaysInSubscription = subscription.duration_days || 30;
    const percentLeft = Math.min(100, Math.max(0, (daysLeft / totalDaysInSubscription) * 100));
    
    // Get subscription color styling
    const colors = getSubscriptionColor(subscription.subscription_type);
    
    return (
      <div className={`bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden`}>
        <div className={`${colors.background} py-4 px-6 text-white relative`}>
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-2xl font-bold">
                {subscription.subscription_type === 'economy' ? (tLang.economyTitle || 'Economy') :
                 subscription.subscription_type === 'vip' ? (tLang.vipTitle || 'VIP') :
                 subscription.subscription_type === 'royal' ? (tLang.royalTitle || 'Royal') :
                 subscription.subscription_type === 'school' ? (tLang.school || 'School') :
                 subscription.subscription_type === 'demo' ? (tLang.demo || 'Demo') : 
                 subscription.subscription_type}
              </h2>
              <p className="mt-1 opacity-90">
                {tLang.activeSubscription || "Active subscription"}
              </p>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold">
                {daysLeft}
              </div>
              <p className="text-sm opacity-90">
                {tLang.daysLeft || "days left"}
              </p>
            </div>
          </div>
          
          {/* Time Progress Bar */}
          <div className="mt-4">
            <div className="w-full bg-white bg-opacity-20 rounded-full h-2.5">
              <div 
                className="h-2.5 rounded-full bg-white" 
                style={{ width: `${percentLeft}%` }}
              ></div>
            </div>
          </div>
        </div>
        
        <div className="py-4 px-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                {tLang.validUntil || "Valid until"}
              </div>
              <div className="text-lg font-medium text-gray-900 dark:text-white">
                {new Date(subscription.expiry_date).toLocaleDateString()}
              </div>
            </div>
            
            <div className="mt-3 md:mt-0">
              <div className="text-sm text-gray-500 dark:text-gray-400">
                {tLang.purchasedOn || "Приобретена"}
              </div>
              <div className="text-lg font-medium text-gray-900 dark:text-white">
                {new Date(subscription.created_at).toLocaleDateString()}
              </div>
            </div>
          </div>
          
          {subscription.auto_renewal && (
            <div className="flex justify-between items-center border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
              <div className="flex items-center text-gray-900 dark:text-white">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 text-green-500" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" />
                </svg>
                {tLang.autoRenewal || "Auto-renewal"}
              </div>
              
              <button
                type="button"
                onClick={cancelAutoRenewal}
                className="flex items-center text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
                {tLang.cancelAutoRenewal || "Cancel auto-renewal"}
              </button>
            </div>
          )}
        </div>
      </div>
    );
  };

  // Render gift options
  const renderGiftOptions = () => {
    if (!isGiftMode) return null;
    
    return (
      <div className="mt-6 p-6 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
          {tLang.giftOptions || "Gift Options"}
        </h3>
        
        <div className="flex space-x-4 mb-5">
          <button
            type="button"
            className={`px-4 py-2 rounded-md transition ${
              giftOption === 'iin' 
                ? 'bg-primary-500 text-white' 
                : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-600'
            }`}
            onClick={() => setGiftOption('iin')}
          >
            {tLang.giftByIIN || "Gift by IIN"}
          </button>
          
          <button
            type="button"
            className={`px-4 py-2 rounded-md transition ${
              giftOption === 'promo' 
                ? 'bg-primary-500 text-white' 
                : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-600'
            }`}
            onClick={() => setGiftOption('promo')}
          >
            {tLang.buyAsPromo || "Buy as Promo Code"}
          </button>
        </div>
        
        {giftOption === 'iin' ? (
          <div>
            <label htmlFor="giftIIN" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              {tLang.enterRecipientIIN || "Enter recipient's IIN"}
            </label>
            <input
              id="giftIIN"
              type="text"
              className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-md focus:ring-primary-500 focus:border-primary-500 dark:bg-gray-700 dark:text-white"
              placeholder={tLang.enterIIN || "Enter IIN"}
              value={giftIIN}
              onChange={(e) => setGiftIIN(e.target.value)}
              maxLength={12}
            />
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              {tLang.giftByIINDescription || "The subscription will be automatically activated on the account with the specified IIN"}
            </p>
          </div>
        ) : (
          <div>
            <p className="text-gray-700 dark:text-gray-300">
              {tLang.promoCodeExplanation || "You will receive a unique promo code that can be activated in the 'Activate Promo Code' section"}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              {tLang.promoCodeNote || "The promo code will be valid for 90 days from the date of purchase"}
            </p>
          </div>
        )}
        
        <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/10 rounded-lg">
          <div className="flex justify-between items-center">
            <span className="text-gray-700 dark:text-gray-300">
              {tLang.paymentSource || "Payment Source"}:
            </span>
            <span className="font-medium text-gray-900 dark:text-white">
              {tLang.fromBalance || "С баланса аккаунта"}
            </span>
          </div>
        </div>
      </div>
    );
  };

  // Render subscription duration selection
  const renderDurationSelection = () => {
    return (
      <div className="mb-8">
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-6 text-center">
          {tLang.chooseSubscriptionDuration || "Выберите срок подписки"}
        </h3>
        
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-4xl mx-auto">
          {/* 1 Month */}
          <div 
            className={`relative py-6 px-8 rounded-2xl transition-all duration-300 border-2 cursor-pointer group ${
              selectedDuration === 1 
                ? selectedSubscriptionType === 'economy' 
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/5 shadow-lg' 
                  : selectedSubscriptionType === 'vip' 
                    ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/5 shadow-lg' 
                    : 'border-amber-500 bg-amber-50 dark:bg-amber-900/5 shadow-lg'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-md'
            }`}
            onClick={() => setSelectedDuration(1)}
          >
            <div className="text-center">
              <div className="flex justify-center mb-3">
                <span className={`inline-block h-6 w-6 rounded-full border-2 ${
                  selectedDuration === 1 
                    ? selectedSubscriptionType === 'economy' 
                      ? 'bg-blue-500 border-blue-500' 
                      : selectedSubscriptionType === 'vip' 
                        ? 'bg-purple-500 border-purple-500' 
                        : 'bg-amber-500 border-amber-500'
                    : 'bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600'
                } flex items-center justify-center`}>
                  {selectedDuration === 1 && (
                    <svg className="h-4 w-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                </span>
              </div>
              <h4 className="text-xl font-bold text-gray-900 dark:text-white mb-2">{tLang.month1 || "1 месяц"}</h4>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
                {tLang.standardPriceLabel || "Стандартная цена"}
              </p>
              <div className="text-lg font-semibold text-gray-900 dark:text-white">
                {formatMoney(getSubscriptionPrice(selectedSubscriptionType, 1))}
              </div>
            </div>
          </div>
          
          {/* 3 Months */}
          <div 
            className={`relative py-6 px-8 rounded-2xl transition-all duration-300 border-2 cursor-pointer group ${
              selectedDuration === 3 
                ? selectedSubscriptionType === 'economy' 
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/5 shadow-lg' 
                  : selectedSubscriptionType === 'vip' 
                    ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/5 shadow-lg' 
                    : 'border-amber-500 bg-amber-50 dark:bg-amber-900/5 shadow-lg'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-md'
            }`}
            onClick={() => setSelectedDuration(3)}
          >
            <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
              <span className="bg-green-500 text-white text-xs px-3 py-1 rounded-full font-bold">
                {tLang.save || "Экономия"} 5%
              </span>
            </div>
            <div className="text-center">
              <div className="flex justify-center mb-3">
                <span className={`inline-block h-6 w-6 rounded-full border-2 ${
                  selectedDuration === 3 
                    ? selectedSubscriptionType === 'economy' 
                      ? 'bg-blue-500 border-blue-500' 
                      : selectedSubscriptionType === 'vip' 
                        ? 'bg-purple-500 border-purple-500' 
                        : 'bg-amber-500 border-amber-500'
                    : 'bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600'
                } flex items-center justify-center`}>
                  {selectedDuration === 3 && (
                    <svg className="h-4 w-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                </span>
              </div>
              <h4 className="text-xl font-bold text-gray-900 dark:text-white mb-2">{tLang.months3 || "3 месяца"}</h4>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
                {tLang.savings || "Экономия"} {formatMoney(getSubscriptionPrice(selectedSubscriptionType, 1) * 3 - getSubscriptionPrice(selectedSubscriptionType, 3))}
              </p>
              <div className="text-lg font-semibold text-gray-900 dark:text-white">
                {formatMoney(getSubscriptionPrice(selectedSubscriptionType, 3))}
              </div>
              <div className="text-sm text-gray-500 line-through">
                {formatMoney(getSubscriptionPrice(selectedSubscriptionType, 1) * 3)}
              </div>
            </div>
          </div>
          
          {/* 6 Months */}
          <div 
            className={`relative py-6 px-8 rounded-2xl transition-all duration-300 border-2 cursor-pointer group ${
              selectedDuration === 6 
                ? selectedSubscriptionType === 'economy' 
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/5 shadow-lg' 
                  : selectedSubscriptionType === 'vip' 
                    ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/5 shadow-lg' 
                    : 'border-amber-500 bg-amber-50 dark:bg-amber-900/5 shadow-lg'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-md'
            }`}
            onClick={() => setSelectedDuration(6)}
          >
            <div className="absolute -top-5 left-1/2 transform -translate-x-1/2 z-10">
              <span className={`inline-block text-white text-sm px-4 py-2 rounded-full font-bold shadow-lg whitespace-nowrap ${
                selectedSubscriptionType === 'economy' 
                  ? 'bg-blue-500' 
                  : selectedSubscriptionType === 'vip' 
                    ? 'bg-purple-500' 
                    : 'bg-amber-500'
              }`}>
                🏆 {tLang.bestValue || "Выгодно"}
              </span>
            </div>
            <div className="text-center">
              <div className="flex justify-center mb-3">
                <span className={`inline-block h-6 w-6 rounded-full border-2 ${
                  selectedDuration === 6 
                    ? selectedSubscriptionType === 'economy' 
                      ? 'bg-blue-500 border-blue-500' 
                      : selectedSubscriptionType === 'vip' 
                        ? 'bg-purple-500 border-purple-500' 
                        : 'bg-amber-500 border-amber-500'
                    : 'bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600'
                } flex items-center justify-center`}>
                  {selectedDuration === 6 && (
                    <svg className="h-4 w-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                </span>
              </div>
              <h4 className="text-xl font-bold text-gray-900 dark:text-white mb-2">{tLang.months6 || "6 месяцев"}</h4>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
                {tLang.savings || "Экономия"} {formatMoney(getSubscriptionPrice(selectedSubscriptionType, 1) * 6 - getSubscriptionPrice(selectedSubscriptionType, 6))}
              </p>
              <div className="text-lg font-semibold text-gray-900 dark:text-white">
                {formatMoney(getSubscriptionPrice(selectedSubscriptionType, 6))}
              </div>
              <div className="text-sm text-gray-500 line-through">
                {formatMoney(getSubscriptionPrice(selectedSubscriptionType, 1) * 6)}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Render purchase options
  const renderPurchaseOptions = () => {
    const currentPrice = getSubscriptionPrice(selectedSubscriptionType, selectedDuration);
    const oldPrice = getOldPrice(selectedSubscriptionType, selectedDuration);
    const savings = oldPrice - currentPrice;
    const savingsPercent = Math.round((savings / oldPrice) * 100);
    
    return (
      <div className="max-w-4xl mx-auto">
        {/* Gift Mode Toggle */}
        <div className="mb-8 text-center">
          <div className="inline-flex bg-gray-100 dark:bg-gray-800 rounded-2xl p-2">
            <button
              type="button"
              onClick={() => setIsGiftMode(false)}
              className={`px-6 py-3 rounded-xl font-semibold transition-all ${
                !isGiftMode
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-md'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              🛒 {tLang.forMyself || "Для себя"}
            </button>
            <button
              type="button"
              onClick={() => setIsGiftMode(true)}
              className={`px-6 py-3 rounded-xl font-semibold transition-all ${
                isGiftMode
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-md'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              🎁 {tLang.asGift || "В подарок"}
            </button>
          </div>
        </div>

        {/* Subscription Types */}
        {renderSubscriptionTypes()}
        
        {/* Gift Options */}
        {renderGiftOptions()}
        
        {/* Duration Selection */}
        {renderDurationSelection()}
        
        {/* Purchase Summary - Large and Clear */}
        <div className="bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded-3xl shadow-xl border border-gray-200 dark:border-gray-700 p-8 mb-8">
          <div className="text-center mb-8">
            <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
              📋 {tLang.orderDetails || "Детали заказа"}
            </h3>
            
            {/* Selected Plan Info */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 mb-6 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-center mb-4">
                <div className={`p-3 rounded-full mr-4 ${
                  selectedSubscriptionType === 'economy' ? 'bg-blue-500' :
                  selectedSubscriptionType === 'vip' ? 'bg-purple-500' : 'bg-amber-500'
                } text-white`}>
                  {selectedSubscriptionType === 'economy' ? '🪙' :
                   selectedSubscriptionType === 'vip' ? '⭐' : '👑'}
                </div>
                <div>
                  <h4 className="text-xl font-bold text-gray-900 dark:text-white">
                    {selectedSubscriptionType === 'economy' ? (tLang.planEconomy || 'Тариф Эконом') :
                     selectedSubscriptionType === 'vip' ? (tLang.planVIP || 'Тариф VIP') : (tLang.planRoyal || 'Тариф Роял')}
                  </h4>
                  <p className="text-gray-500 dark:text-gray-400">
                    {selectedDuration === 1 ? (tLang.duration1Month || '1 месяц') : 
                     selectedDuration === 3 ? (tLang.duration3Months || '3 месяца') : (tLang.duration6Months || '6 месяцев')}
                  </p>
                </div>
              </div>
              
              {/* Price Breakdown */}
              <div className="space-y-3">
                <div className="flex justify-between items-center text-lg">
                  <span className="text-gray-600 dark:text-gray-400">{tLang.originalPrice || "Обычная цена"}:</span>
                  <span className="text-gray-500 line-through">{formatMoney(oldPrice)}</span>
                </div>
                <div className="flex justify-between items-center text-lg">
                  <span className="text-gray-600 dark:text-gray-400">{tLang.yourDiscount || "Ваша скидка"}:</span>
                  <span className="text-green-600 font-semibold">-{formatMoney(savings)} ({savingsPercent}%)</span>
                </div>
                <hr className="border-gray-200 dark:border-gray-700" />
                <div className="flex justify-between items-center text-2xl font-bold">
                  <span className="text-gray-900 dark:text-white">{tLang.totalToPay || "К оплате"}:</span>
                  <span className={`${
                    selectedSubscriptionType === 'economy' ? 'text-blue-600' :
                    selectedSubscriptionType === 'vip' ? 'text-purple-600' : 'text-amber-600'
                  }`}>
                    {formatMoney(currentPrice)}
                  </span>
                </div>
              </div>
            </div>
          </div>
          
          {/* User Balance */}
          <div className="bg-blue-50 dark:bg-blue-900/10 rounded-2xl p-6 mb-6 border border-blue-200 dark:border-blue-800">
            <div className="flex justify-between items-center">
              <div className="flex items-center">
                <div className="bg-blue-500 p-2 rounded-full mr-3">
                  <svg className="h-6 w-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <p className="text-lg font-semibold text-gray-900 dark:text-white">{tLang.yourBalance || "Ваш баланс"}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{tLang.willBeDeducted || "Будет списано с баланса"}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{formatMoney(balance)}</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {tLang.afterPurchase || "После покупки"}: {formatMoney(balance - currentPrice)}
                </p>
              </div>
            </div>
            
            {/* Insufficient Balance Warning */}
            {balance < currentPrice && (
              <div className="mt-4 p-4 bg-red-100 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
                <div className="flex items-center">
                  <svg className="h-6 w-6 text-red-500 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.081 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                  <div>
                    <p className="font-semibold text-red-800 dark:text-red-200">{tLang.insufficientFunds || "Недостаточно средств"}</p>
                    <p className="text-sm text-red-600 dark:text-red-300">
                      {tLang.needToTopUp || "Нужно пополнить баланс на"} {formatMoney(currentPrice - balance)}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setActiveTab('balance')}
                  className="mt-3 w-full bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded-lg transition-colors"
                >
                  💳 {tLang.topUpBalance || "Пополнить баланс"}
                </button>
              </div>
            )}
          </div>
          
          {/* Purchase Button - Large and Prominent */}
          <button
            type="button"
            onClick={isGiftMode ? handlePurchaseGift : handlePurchaseSubscription}
            disabled={purchaseLoading || balance < currentPrice}
            className={`w-full py-6 px-8 rounded-2xl font-bold text-xl transition-all duration-200 shadow-lg ${
              balance < currentPrice
                ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'
                : selectedSubscriptionType === 'economy'
                  ? 'bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white shadow-blue-200 dark:shadow-blue-900/20 hover:shadow-xl'
                  : selectedSubscriptionType === 'vip'
                    ? 'bg-gradient-to-r from-purple-500 to-purple-600 hover:from-purple-600 hover:to-purple-700 text-white shadow-purple-200 dark:shadow-purple-900/20 hover:shadow-xl'
                    : 'bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white shadow-amber-200 dark:shadow-amber-900/20 hover:shadow-xl'
            }`}
          >
            {purchaseLoading ? (
              <div className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-3 h-6 w-6 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                {tLang.processingPayment || "Обработка платежа..."}
              </div>
            ) : balance < currentPrice ? (
              `❌ ${tLang.insufficientFunds || "Недостаточно средств"}`
            ) : (
              <div className="flex items-center justify-center">
                <span className="mr-3">
                  {isGiftMode ? '🎁' : '🛒'}
                </span>
                {isGiftMode ? `${tLang.giftFor || "Подарить за"} ${formatMoney(currentPrice)}` : `${tLang.buyFor || "Купить за"} ${formatMoney(currentPrice)}`}
                <span className="ml-3">
                  {selectedSubscriptionType === 'economy' ? '🪙' :
                   selectedSubscriptionType === 'vip' ? '⭐' : '👑'}
                </span>
              </div>
            )}
          </button>
          
          {/* Security Info */}
          <div className="mt-6 text-center">
            <p className="text-sm text-gray-500 dark:text-gray-400 flex items-center justify-center">
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              🔒 {tLang.securityInfo || "Безопасная оплата • Мгновенная активация • Гарантия возврата"}
            </p>
          </div>
        </div>
      </div>
    );
  };
  
  // Render balance and promo code section
  const renderBalanceAndPromo = () => {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Balance Top-Up Card */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md overflow-hidden border border-gray-200 dark:border-gray-700 h-full">
          <div className="p-6 flex flex-col h-full">
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
              {tLang.topUpBalance || "Пополнить баланс"}
            </h3>
            
            <form onSubmit={handleTopUp} className="flex flex-col h-full justify-between space-y-4">
              <div>
                <label htmlFor="topUpAmount" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {tLang.amount || "Сумма"}
                </label>
                <div className="relative">
                  <input
                    type="number"
                    id="topUpAmount"
                    value={topUpAmount}
                    onChange={(e) => setTopUpAmount(e.target.value)}
                    min="500"
                    placeholder={tLang.enterAmount || "Введите сумму"}
                    className="w-full pl-3 pr-10 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-primary-500 focus:border-primary-500 dark:bg-gray-700 dark:text-white"
                    required
                  />
                  <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-gray-500 dark:text-gray-400">
                    ₸
                  </div>
                </div>
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 flex items-center">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {tLang.minAmount || "Минимальная сумма"}: 500 ₸
                </p>
              </div>
            
              
              <button
                type="submit"
                className="w-full py-3 px-4 bg-primary-600 hover:bg-primary-700 disabled:bg-primary-400 dark:disabled:bg-primary-800 text-white rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800"
                disabled={purchaseLoading}
              >
                {purchaseLoading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    {tLang.processing || "Обработка..."}
                  </span>
                ) : (
                  tLang.topUp || "Пополнить"
                )}
              </button>
            </form>
          </div>
        </div>
        
        {/* Activate Promo Code Card */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md overflow-hidden border border-gray-200 dark:border-gray-700 h-full">
          <div className="p-6 flex flex-col h-full">
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
              {tLang.activatePromoCode || "Активировать промокод"}
            </h3>
            
            <p className="mb-4 text-gray-600 dark:text-gray-400">
              {tLang.promoDescription || "Введите промокод для активации подписки или получения бонуса"}
            </p>
            
            <form onSubmit={handleActivatePromo} className="flex flex-col h-full justify-between space-y-4">
              <div>
                <label htmlFor="promoCode" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {tLang.promoCode || "Промокод"}
                </label>
                <input
                  id="promoCode"
                  type="text"
                  required
                  minLength="6"
                  className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-primary-500 focus:border-primary-500 dark:bg-gray-700 dark:text-white"
                  placeholder={tLang.enterPromoCode || "Введите промокод"}
                />
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                  {tLang.promoCodeDescription || "Введите промокод для активации подписки или получения бонуса"}
                </p>
              </div>
              
              <div className="mt-auto pt-4">
                <button
                  type="submit"
                  disabled={purchaseLoading}
                  className="w-full py-3 px-4 bg-primary-600 hover:bg-primary-700 disabled:bg-primary-400 dark:disabled:bg-primary-800 text-white rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800"
                >
                  {purchaseLoading ? (
                    <span className="flex items-center justify-center">
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      {tLang.processing || "Обработка..."}
                    </span>
                  ) : (
                    tLang.activate || "Активировать"
                  )}
                </button>
              </div>
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
            {tLang.subscriptionManagement || "Subscription Management"}
          </h1>
          <p className="text-gray-600 dark:text-gray-300">
            {tLang.subscriptionDescription || "Here you can manage your subscription, top up your balance, or activate a promo code"}
          </p>
        </div>
      </div>
      
      {/* Loading State Overlay */}
      {purchaseLoading && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-xl max-w-md w-full">
            <div className="flex flex-col items-center">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500 mb-4"></div>
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                {tLang.processing || "Processing..."}
              </h3>
              <p className="text-gray-600 dark:text-gray-400 text-center">
                {tLang.pleaseWait || "Please wait while we process your request"}
              </p>
            </div>
          </div>
        </div>
      )}
      
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
            {tLang.mySubscription || "My Subscription"}
          </button>
          <button
            onClick={() => {
              setActiveTab('buy');
              setIsGiftMode(false);
            }}
            className={`flex-1 py-4 px-6 text-center font-medium ${
              activeTab === 'buy'
                ? 'text-primary-600 dark:text-primary-400 border-b-2 border-primary-500'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
            }`}
          >
            {tLang.buySubscription || "Buy Subscription"}
          </button>
          <button
            onClick={() => setActiveTab('balance')}
            className={`flex-1 py-4 px-6 text-center font-medium ${
              activeTab === 'balance'
                ? 'text-primary-600 dark:text-primary-400 border-b-2 border-primary-500'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
            }`}
          >
            {tLang.balanceAndPromo || "Balance and Promo Codes"}
          </button>
        </div>
      </div>
      
      {/* Tab Content */}
      {activeTab === 'subscription' && renderCurrentSubscription()}
      {activeTab === 'buy' && renderPurchaseOptions()}
      {activeTab === 'balance' && renderBalanceAndPromo()}
    </div>
  );
};

export default SubscriptionPage; 