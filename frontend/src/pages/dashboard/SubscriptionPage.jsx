import React, { useState, useEffect } from 'react';
import { useLanguage } from '../../contexts/LanguageContext';
import { translations } from '../../translations/translations';
import { toast } from 'react-toastify';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

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
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState(null);
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
    fetchSubscription();
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
        setSubscription(data.subscription);
        setBalance(data.balance);
      }
    } catch (error) {
      console.error('Error fetching subscription:', error);
    } finally {
      setLoading(false);
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
      'economy': 5000,
      'vip': 10000,
      'royal': 15000
    }[type] || 5000;
    
    // Apply discount based on selected duration
    let discount = 0;
    if (months === 3) discount = 0.05; // 5% discount for 3 months
    if (months === 6) discount = 0.10; // 10% discount for 6 months
    
    return basePrice * months * (1 - discount);
  };
  
  // Clear error and success messages
  const clearMessages = () => {
    setError(null);
    setSuccess(null);
  };
  
  // Handle subscription purchase
  const handlePurchaseSubscription = async (event) => {
    event.preventDefault();
    clearMessages();
    
    // Calculate price
    const price = getSubscriptionPrice(selectedSubscriptionType, selectedDuration);
    
    // Navigate to the payment page with selected subscription details
    navigate('/dashboard/payment', {
      state: {
        paymentDetails: {
          subscriptionType: selectedSubscriptionType,
          duration: selectedDuration,
          price: price,
          date: new Date().toLocaleDateString(),
          orderId: `ORD-${Math.floor(Math.random() * 100000)}`
        }
      }
    });
  };
  
  // Handle gift purchase
  const handlePurchaseGift = async (event) => {
    event.preventDefault();
    clearMessages();
    
    // Validate IIN if gift by IIN is selected
    if (giftOption === 'iin' && (!giftIIN || giftIIN.length !== 12)) {
      setError(tLang.invalidIIN || "Please enter a valid 12-digit IIN");
      return;
    }
    
    // Calculate price based on subscription type and duration
    const price = getSubscriptionPrice(selectedSubscriptionType, selectedDuration);
    
    // Navigate to the payment page with gift details
    navigate('/dashboard/payment', {
      state: {
        paymentDetails: {
          subscriptionType: selectedSubscriptionType,
          duration: selectedDuration,
          price: price,
          date: new Date().toLocaleDateString(),
          orderId: `ORD-${Math.floor(Math.random() * 100000)}`,
          isGift: true,
          giftOption: giftOption,
          giftIIN: giftOption === 'iin' ? giftIIN : null
        }
      }
    });
  };
  
  // Handle balance top-up
  const handleTopUp = async (event) => {
    event.preventDefault();
    clearMessages();
    
    // Get the selected amount from the form
    const formElement = event.target;
    const amount = formElement.querySelector('#amount')?.value || topUpAmount;
    
    if (!amount || isNaN(amount) || parseInt(amount) < 500) {
      setError(tLang.minAmountError || "Минимальная сумма для пополнения: 500 ₸");
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
  };
  
  // Handle promo code activation
  const handleActivatePromo = async (event) => {
    event.preventDefault();
    clearMessages();
    
    try {
      // Get promo code from the form
      const formElement = event.target;
      const promoCode = formElement.querySelector('#promoCode')?.value;
      
      if (!promoCode || promoCode.trim() === '') {
        setError(tLang.promoCodeRequired || "Пожалуйста, введите промокод");
        return;
      }
      
      setPurchaseLoading(true);
      
      // Make API request to activate promo code
      const response = await axios.post('/api/subscriptions/activate-promo', { promo_code: promoCode.trim() }, {
        withCredentials: true
      });
      
      if (response.status === 200) {
        setSuccess(
          response.data.message || 
          tLang.promoCodeActivated || 
          "Промокод успешно активирован"
        );
        
        // Clear input field
        formElement.querySelector('#promoCode').value = '';
        
        // Refresh subscription data
        await fetchSubscription();
      }
    } catch (error) {
      console.error('Error activating promo code:', error);
      setError(
        error.response?.data?.message || 
        tLang.promoCodeError || 
        "Произошла ошибка при активации промокода. Пожалуйста, проверьте его правильность и попробуйте снова."
      );
    } finally {
      setPurchaseLoading(false);
    }
  };
  
  // Handle gift by IIN
  const handleGiftByIIN = async (event) => {
    event.preventDefault();
    clearMessages();
    
    if (!giftIIN || giftIIN.length !== 12) {
      setError(tLang.invalidIIN || "Please enter a valid 12-digit IIN");
      return;
    }
    
    // Calculate price based on subscription type and duration
    const price = getSubscriptionPrice(selectedSubscriptionType, selectedDuration);
    
    // Navigate to the payment page with gift details
    navigate('/dashboard/payment', {
      state: {
        paymentDetails: {
          subscriptionType: selectedSubscriptionType,
          duration: selectedDuration,
          price: price,
          date: new Date().toLocaleDateString(),
          orderId: `ORD-${Math.floor(Math.random() * 100000)}`,
          isGift: true,
          giftOption: 'iin',
          giftIIN: giftIIN
        }
      }
    });
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
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6">
          {tLang.choosePlanSubtitle || "Choose a plan that suits you"}
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Economy Plan */}
          <div 
            className={`relative overflow-hidden rounded-2xl transition-all duration-300 border-2 ${
              selectedSubscriptionType === 'economy' 
                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/10 shadow-lg shadow-blue-100 dark:shadow-blue-900/5' 
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
            onClick={() => setSelectedSubscriptionType('economy')}
          >
            <div className="p-6 flex flex-col h-full">
              <div className="flex items-center mb-4">
                <div className={`p-2.5 rounded-full mr-3 ${selectedSubscriptionType === 'economy' ? 'bg-blue-500' : 'bg-gray-200 dark:bg-gray-700'} text-white`}>
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white">{tLang.economyTitle || "Economy"}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{tLang.basicPlan || "Basic plan"}</p>
                </div>
              </div>
              
              <div className="mb-4">
                <div className="flex items-baseline">
                  <span className="text-3xl font-extrabold text-gray-900 dark:text-white">{formatMoney(getSubscriptionPrice('economy'))}</span>
                  <span className="text-sm ml-1 text-gray-500 dark:text-gray-400">/ {tLang.month || "month"}</span>
                </div>
              </div>
              
              <ul className="space-y-3 mb-6 flex-grow min-h-[200px]">
                <li className="flex items-start">
                  <svg className="h-5 w-5 text-blue-500 mt-0.5 mr-2 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300">{tLang.fullTestAccess || "Access to all tests"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-5 w-5 text-blue-500 mt-0.5 mr-2 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300">{tLang.basicStatistics || "Basic statistics"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-5 w-5 text-blue-500 mt-0.5 mr-2 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300">{tLang.emailSupport || "Email support"}</span>
                </li>
              </ul>
              
              <button
                type="button"
                className={`w-full py-2.5 px-4 rounded-lg text-center font-medium transition-colors mt-auto ${
                  selectedSubscriptionType === 'economy'
                    ? 'bg-blue-500 hover:bg-blue-600 text-white'
                    : 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200'
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedSubscriptionType('economy');
                }}
              >
                {selectedSubscriptionType === 'economy' ? (tLang.selected || "Selected") : (tLang.select || "Select")}
              </button>
            </div>
          </div>

          {/* VIP Plan */}
          <div 
            className={`relative overflow-hidden rounded-2xl transition-all duration-300 border-2 ${
              selectedSubscriptionType === 'vip' 
                ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/10 shadow-lg shadow-purple-100 dark:shadow-purple-900/5' 
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
            onClick={() => setSelectedSubscriptionType('vip')}
          >
            <div className="absolute top-4 right-4">
              <span className="bg-purple-500 text-white text-xs px-2 py-1 rounded-full font-medium">
                {tLang.popular || "Popular"}
              </span>
            </div>
            <div className="p-6 flex flex-col h-full">
              <div className="flex items-center mb-4">
                <div className={`p-2.5 rounded-full mr-3 ${selectedSubscriptionType === 'vip' ? 'bg-purple-500' : 'bg-gray-200 dark:bg-gray-700'} text-white`}>
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white">{tLang.vipTitle || "VIP"}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{tLang.advancedPlan || "Advanced plan"}</p>
                </div>
              </div>
              
              <div className="mb-4">
                <div className="flex items-baseline">
                  <span className="text-3xl font-extrabold text-gray-900 dark:text-white">{formatMoney(getSubscriptionPrice('vip'))}</span>
                  <span className="text-sm ml-1 text-gray-500 dark:text-gray-400">/ {tLang.month || "month"}</span>
                </div>
              </div>
              
              <ul className="space-y-3 mb-6 flex-grow min-h-[200px]">
                <li className="flex items-start">
                  <svg className="h-5 w-5 text-purple-500 mt-0.5 mr-2 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300">{tLang.allEconomyFeatures || "All Economy features"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-5 w-5 text-purple-500 mt-0.5 mr-2 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300">{tLang.detailedStats || "Detailed statistics"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-5 w-5 text-purple-500 mt-0.5 mr-2 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300">{tLang.createReferrals || "Create referral links"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-5 w-5 text-purple-500 mt-0.5 mr-2 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300">{tLang.prioritySupport || "Priority support"}</span>
                </li>
              </ul>
              
              <button
                type="button"
                className={`w-full py-2.5 px-4 rounded-lg text-center font-medium transition-colors mt-auto ${
                  selectedSubscriptionType === 'vip'
                    ? 'bg-purple-500 hover:bg-purple-600 text-white'
                    : 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200'
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedSubscriptionType('vip');
                }}
              >
                {selectedSubscriptionType === 'vip' ? (tLang.selected || "Selected") : (tLang.select || "Select")}
              </button>
            </div>
          </div>

          {/* Royal Plan */}
          <div 
            className={`relative overflow-hidden rounded-2xl transition-all duration-300 border-2 ${
              selectedSubscriptionType === 'royal' 
                ? 'border-amber-500 bg-amber-50 dark:bg-amber-900/10 shadow-lg shadow-amber-100 dark:shadow-amber-900/5' 
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
            onClick={() => setSelectedSubscriptionType('royal')}
          >
            <div className="p-6 flex flex-col h-full">
              <div className="flex items-center mb-4">
                <div className={`p-2.5 rounded-full mr-3 ${selectedSubscriptionType === 'royal' ? 'bg-amber-500' : 'bg-gray-200 dark:bg-gray-700'} text-white`}>
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white">{tLang.royalTitle || "Royal"}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{tLang.premiumPlan || "Premium plan"}</p>
                </div>
              </div>
              
              <div className="mb-4">
                <div className="flex items-baseline">
                  <span className="text-3xl font-extrabold text-gray-900 dark:text-white">{formatMoney(getSubscriptionPrice('royal'))}</span>
                  <span className="text-sm ml-1 text-gray-500 dark:text-gray-400">/ {tLang.month || "month"}</span>
                </div>
              </div>
              
              <ul className="space-y-3 mb-6 flex-grow min-h-[200px]">
                <li className="flex items-start">
                  <svg className="h-5 w-5 text-amber-500 mt-0.5 mr-2 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300">{tLang.allVIPFeatures || "All VIP features"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-5 w-5 text-amber-500 mt-0.5 mr-2 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300">{tLang.exclusiveContent || "Exclusive content"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-5 w-5 text-amber-500 mt-0.5 mr-2 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300">{tLang.premiumSupport || "Premium 24/7 support"}</span>
                </li>
                <li className="flex items-start">
                  <svg className="h-5 w-5 text-amber-500 mt-0.5 mr-2 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700 dark:text-gray-300">{tLang.specialDiscounts || "Special discounts on additional services"}</span>
                </li>
              </ul>
              
              <button
                type="button"
                className={`w-full py-2.5 px-4 rounded-lg text-center font-medium transition-colors mt-auto ${
                  selectedSubscriptionType === 'royal'
                    ? 'bg-amber-500 hover:bg-amber-600 text-white'
                    : 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200'
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedSubscriptionType('royal');
                }}
              >
                {selectedSubscriptionType === 'royal' ? (tLang.selected || "Selected") : (tLang.select || "Select")}
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
    
    // Get subscription color styling
    const colors = getSubscriptionColor(subscription.subscription_type);
    
    return (
      <div className={`bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden`}>
        <div className={`${colors.background} py-4 px-6 text-white`}>
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
                {tLang.purchasedOn || "Purchased on"}
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
      </div>
    );
  };

  // Render subscription duration selection
  const renderDurationSelection = () => {
    return (
      <div className="mb-8">
        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
          {tLang.chooseSubscriptionDuration || "Choose subscription duration"}
        </h3>
        
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* 1 Month */}
          <div 
            className={`relative py-4 px-5 rounded-xl transition-all duration-200 border-2 ${
              selectedDuration === 1 
                ? selectedSubscriptionType === 'economy' 
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/5' 
                  : selectedSubscriptionType === 'vip' 
                    ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/5' 
                    : 'border-amber-500 bg-amber-50 dark:bg-amber-900/5'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
            onClick={() => setSelectedDuration(1)}
          >
            <div className="flex justify-between items-center">
              <div>
                <span className="block text-gray-900 dark:text-white font-medium">{tLang.month1 || "1 month"}</span>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {tLang.standardPrice || "Standard price"}
                </span>
              </div>
              <div className="flex items-center">
                <span className={`inline-block h-5 w-5 rounded-full ${
                  selectedDuration === 1 
                    ? selectedSubscriptionType === 'economy' 
                      ? 'bg-blue-500' 
                      : selectedSubscriptionType === 'vip' 
                        ? 'bg-purple-500' 
                        : 'bg-amber-500'
                    : 'bg-gray-200 dark:bg-gray-700'
                } flex items-center justify-center`}>
                  {selectedDuration === 1 && (
                    <svg className="h-3 w-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                </span>
              </div>
            </div>
          </div>
          
          {/* 3 Months */}
          <div 
            className={`relative py-4 px-5 rounded-xl transition-all duration-200 border-2 ${
              selectedDuration === 3 
                ? selectedSubscriptionType === 'economy' 
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/5' 
                  : selectedSubscriptionType === 'vip' 
                    ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/5' 
                    : 'border-amber-500 bg-amber-50 dark:bg-amber-900/5'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
            onClick={() => setSelectedDuration(3)}
          >
            <div className="flex justify-between items-center">
              <div>
                <span className="block text-gray-900 dark:text-white font-medium">{tLang.months3 || "3 months"}</span>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {tLang.save || "Save"} 5%
                </span>
              </div>
              <div className="flex items-center">
                <span className={`inline-block h-5 w-5 rounded-full ${
                  selectedDuration === 3 
                    ? selectedSubscriptionType === 'economy' 
                      ? 'bg-blue-500' 
                      : selectedSubscriptionType === 'vip' 
                        ? 'bg-purple-500' 
                        : 'bg-amber-500'
                    : 'bg-gray-200 dark:bg-gray-700'
                } flex items-center justify-center`}>
                  {selectedDuration === 3 && (
                    <svg className="h-3 w-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                </span>
              </div>
            </div>
          </div>
          
          {/* 6 Months */}
          <div 
            className={`relative py-4 px-5 rounded-xl transition-all duration-200 border-2 ${
              selectedDuration === 6 
                ? selectedSubscriptionType === 'economy' 
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/5' 
                  : selectedSubscriptionType === 'vip' 
                    ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/5' 
                    : 'border-amber-500 bg-amber-50 dark:bg-amber-900/5'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
            onClick={() => setSelectedDuration(6)}
          >
            <div className="absolute -top-3 -right-2">
              <span className={`inline-block px-2 py-1 text-xs font-medium text-white rounded-full ${
                selectedSubscriptionType === 'economy' 
                  ? 'bg-blue-500' 
                  : selectedSubscriptionType === 'vip' 
                    ? 'bg-purple-500' 
                    : 'bg-amber-500'
              }`}>
                {tLang.bestValue || "Best value"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <div>
                <span className="block text-gray-900 dark:text-white font-medium">{tLang.months6 || "6 months"}</span>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {tLang.save || "Save"} 10%
                </span>
              </div>
              <div className="flex items-center">
                <span className={`inline-block h-5 w-5 rounded-full ${
                  selectedDuration === 6 
                    ? selectedSubscriptionType === 'economy' 
                      ? 'bg-blue-500' 
                      : selectedSubscriptionType === 'vip' 
                        ? 'bg-purple-500' 
                        : 'bg-amber-500'
                    : 'bg-gray-200 dark:bg-gray-700'
                } flex items-center justify-center`}>
                  {selectedDuration === 6 && (
                    <svg className="h-3 w-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Render purchase options
  const renderPurchaseOptions = () => {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
        <div className="mb-6 flex justify-between items-center">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">
            {tLang.buySubscription || "Buy Subscription"}
          </h2>
          <button
            type="button"
            onClick={() => setIsGiftMode(!isGiftMode)}
            className={`px-4 py-2 rounded-lg transition ${
              isGiftMode
                ? 'bg-primary-100 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            {isGiftMode ? (tLang.purchaseForSelf || "Purchase for Self") : (tLang.buyAsGift || "Buy as Gift")}
          </button>
        </div>
        
        {/* Subscription Types */}
        {renderSubscriptionTypes()}
        
        {/* Gift Options */}
        {renderGiftOptions()}
        
        {/* Duration Selection */}
        {renderDurationSelection()}
        
        {/* Total Price */}
        <div className="mb-8 p-6 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="flex justify-between items-center">
            <span className="text-lg font-medium text-gray-900 dark:text-white">
              {tLang.totalPrice || "Total Price"}:
            </span>
            <span className="text-2xl font-bold text-gray-900 dark:text-white">
              {formatMoney(getSubscriptionPrice(selectedSubscriptionType, selectedDuration))}
            </span>
          </div>
        </div>
        
        {/* Purchase Button */}
        <div className="flex justify-end">
          <button
            type="button"
            onClick={isGiftMode ? handlePurchaseGift : handlePurchaseSubscription}
            disabled={purchaseLoading}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              selectedSubscriptionType === 'economy'
                ? 'bg-blue-500 hover:bg-blue-600 text-white'
                : selectedSubscriptionType === 'vip'
                  ? 'bg-purple-500 hover:bg-purple-600 text-white'
                  : 'bg-amber-500 hover:bg-amber-600 text-white'
            }`}
          >
            {purchaseLoading ? (
              <span className="flex items-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                {tLang.processing || "Processing..."}
              </span>
            ) : (
              isGiftMode ? (tLang.purchaseGift || "Purchase Gift") : (tLang.buySubscription || "Buy Subscription")
            )}
          </button>
        </div>
      </div>
    );
  };
  
  // Render balance and promo code section
  const renderBalanceAndPromo = () => {
    return (
      <div className="row mt-4">
        <div className="col-md-6 mb-4">
          <div className="card shadow-sm h-100">
            <div className="card-body">
              <h5 className="card-title mb-3">{tLang.topUpBalance || "Пополнить баланс"}</h5>
              <p className="text-muted mb-3">
                {tLang.currentBalance || "Текущий баланс"}: {formatMoney(balance || 0)}
              </p>
              <form onSubmit={handleTopUp}>
                <div className="mb-3">
                  <label htmlFor="topUpAmount" className="form-label">
                    {tLang.amount || "Сумма"}
                  </label>
                  <div className="input-group">
                    <input
                      type="number"
                      className="form-control"
                      id="topUpAmount"
                      value={topUpAmount}
                      onChange={(e) => setTopUpAmount(e.target.value)}
                      min="500"
                      placeholder={tLang.enterAmount || "Введите сумму"}
                      required
                    />
                    <span className="input-group-text">₸</span>
                  </div>
                  <small className="form-text text-muted">
                    {tLang.minAmount || "Минимальная сумма"}: 500 ₸
                  </small>
                </div>
                <button
                  type="submit"
                  className="btn btn-primary w-100"
                  disabled={purchaseLoading}
                >
                  {purchaseLoading ? (
                    <span>
                      <i className="fas fa-circle-notch fa-spin me-2"></i>
                      {tLang.processing || "Обработка..."}
                    </span>
                  ) : (
                    tLang.topUp || "Пополнить"
                  )}
                </button>
              </form>
            </div>
          </div>
        </div>
        
        {/* Activate Promo Code */}
        <div className="col-md-6 mb-4">
          <div className="card shadow-sm h-100">
            <div className="card-body">
              <h5 className="card-title mb-3">{tLang.activatePromoCode || "Активировать промокод"}</h5>
              <p className="mb-3">{tLang.promoDescription || "Введите промокод для активации подписки или получения бонуса"}</p>
              
              <form onSubmit={handleActivatePromo} className="space-y-4">
                <div>
                  <label htmlFor="promoCode" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    {tLang.promoCode || "Promo Code"}
                  </label>
                  <input
                    id="promoCode"
                    type="text"
                    required
                    minLength="6"
                    className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-md focus:ring-primary-500 focus:border-primary-500 dark:bg-gray-700 dark:text-white"
                    placeholder={tLang.enterPromoCode || "Enter promo code"}
                  />
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                    {tLang.promoCodeDescription || "Enter a promo code to activate a subscription or receive a bonus"}
                  </p>
                </div>
                
                <button
                  type="submit"
                  disabled={purchaseLoading}
                  className="w-full px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-70 text-white rounded-lg font-medium transition-colors"
                >
                  {purchaseLoading ? (
                    <span className="flex items-center justify-center">
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      {tLang.processing || "Processing..."}
                    </span>
                  ) : (
                    tLang.activate || "Activate"
                  )}
                </button>
              </form>
            </div>
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
      
      {/* Success and Error Messages */}
      {success && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 text-green-800 dark:text-green-300">
          <div className="flex">
            <svg className="h-5 w-5 mr-2 text-green-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span>{success}</span>
          </div>
        </div>
      )}
      
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-800 dark:text-red-300">
          <div className="flex">
            <svg className="h-5 w-5 mr-2 text-red-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <span>{error}</span>
          </div>
        </div>
      )}
      
      {/* Tabs */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
        <div className="flex border-b border-gray-200 dark:border-gray-700">
          <button
            onClick={() => {
              setActiveTab('subscription');
              clearMessages();
            }}
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
              clearMessages();
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
            onClick={() => {
              setActiveTab('balance');
              clearMessages();
            }}
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