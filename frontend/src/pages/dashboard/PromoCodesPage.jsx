import React, { useState, useEffect } from 'react';
import { useLanguage } from '../../contexts/LanguageContext';
import { translations } from '../../translations/translations';
import { toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { 
  FaCopy, 
  FaCrown, 
  FaCalendarAlt, 
  FaUser, 
  FaCheck, 
  FaBan, 
  FaClock, 
  FaInfoCircle, 
  FaTag, 
  FaUsers 
} from 'react-icons/fa';
import './styles.css';

const PromoCodesPage = () => {
  const { language } = useLanguage();
  const t = translations[language];
  
  const [loading, setLoading] = useState(true);
  const [createdPromoCodes, setCreatedPromoCodes] = useState([]);
  const [usedPromoCodes, setUsedPromoCodes] = useState([]);
  const [expandedCards, setExpandedCards] = useState({});
  const [activeTabs, setActiveTabs] = useState({});

  useEffect(() => {
    fetchPromoCodes();
  }, []);

  const fetchPromoCodes = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/users/my/promo-codes');
      
      if (!response.ok) throw new Error('Failed to fetch promo codes');
      
      const data = await response.json();
      console.log('Response data:', data);
      
      if (data.status === "ok" && data.data) {
        const created = data.data.created_promo_codes || [];
        const used = data.data.used_promo_codes || [];
        
        // Initialize tabs for each promo code
        const initialTabs = {};
        created.forEach(code => {
          initialTabs[code.code] = 'details';
        });
        used.forEach(code => {
          initialTabs[code.code] = 'details';
        });
        setActiveTabs(initialTabs);
        
        setCreatedPromoCodes(created);
        setUsedPromoCodes(used);
      } else {
        throw new Error(data.message || 'Failed to fetch promo codes');
      }
    } catch (error) {
      console.error("Error fetching promo codes:", error);
      toast.error(t.errorFetchingPromoCodes || "Error fetching promo codes");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
      .then(() => toast.success(t.copied || "Copied to clipboard"))
      .catch(() => toast.error(t.failedToCopy || "Failed to copy"));
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString(language === 'ru' ? 'ru-RU' : language === 'kz' ? 'kk-KZ' : 'en-US');
  };
  
  const formatDateTime = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleString(
      language === 'ru' ? 'ru-RU' : language === 'kz' ? 'kk-KZ' : 'en-US',
      { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }
    );
  };

  const getLocalizedText = (ruText, kzText, enText) => {
    switch(language) {
      case 'ru': return ruText;
      case 'kz': return kzText;
      case 'en': return enText;
      default: return ruText;
    }
  };

  const getStatusLabel = (status) => {
    switch(status) {
      case 'active':
        return getLocalizedText('Активен', 'Белсенді', 'Active');
      case 'used':
        return getLocalizedText('Использован', 'Қолданылған', 'Used');
      case 'expired':
        return getLocalizedText('Истек', 'Мерзімі өткен', 'Expired');
      default:
        return status;
    }
  };

  const getActiveStatusDescription = (status) => {
    if (status === 'active') {
      return getLocalizedText(
        'Этот код действителен и может быть использован', 
        'Бұл код жарамды және пайдаланылуы мүмкін', 
        'This code is valid and can be used'
      );
    } else if (status === 'used') {
      return getLocalizedText(
        'Этот код был использован', 
        'Бұл код пайдаланылды', 
        'This code has been used'
      );
    } else {
      return getLocalizedText(
        'Срок действия этого кода истек', 
        'Бұл кодтың мерзімі өтті', 
        'This code has expired'
      );
    }
  };

  const renderStatusBadge = (status) => {
    let bgColorLight = '';
    let bgColorDark = '';
    let textColorLight = '';
    let textColorDark = '';
    let Icon = null;
    
    switch(status) {
      case 'active':
        bgColorLight = 'bg-green-100';
        bgColorDark = 'dark:bg-green-900/30';
        textColorLight = 'text-green-800';
        textColorDark = 'dark:text-green-400';
        Icon = FaCheck;
        break;
      case 'used':
        bgColorLight = 'bg-blue-100';
        bgColorDark = 'dark:bg-blue-900/30';
        textColorLight = 'text-blue-800';
        textColorDark = 'dark:text-blue-400';
        Icon = FaUser;
        break;
      case 'expired':
        bgColorLight = 'bg-red-100';
        bgColorDark = 'dark:bg-red-900/30';
        textColorLight = 'text-red-800';
        textColorDark = 'dark:text-red-400';
        Icon = FaBan;
        break;
      default:
        bgColorLight = 'bg-gray-100';
        bgColorDark = 'dark:bg-gray-800';
        textColorLight = 'text-gray-800';
        textColorDark = 'dark:text-gray-300';
    }
    
    return (
      <span className={`inline-flex items-center px-2.5 py-1.5 rounded-full text-sm font-medium ${bgColorLight} ${bgColorDark} ${textColorLight} ${textColorDark}`}>
        {Icon && <Icon className="mr-1" />}
        {getStatusLabel(status)}
      </span>
    );
  };
  
  const toggleExpand = (codeId) => {
    setExpandedCards(prev => ({
      ...prev,
      [codeId]: !prev[codeId]
    }));
  };
  
  const changeTab = (codeId, tab) => {
    setActiveTabs(prev => ({
      ...prev,
      [codeId]: tab
    }));
  };
  
  const renderSubscriptionBadge = (type) => {
    let bgColorLight = '';
    let bgColorDark = '';
    let textColorLight = '';
    let textColorDark = '';
    
    switch(type) {
      case 'economy':
        bgColorLight = 'bg-blue-100';
        bgColorDark = 'dark:bg-blue-900/30';
        textColorLight = 'text-blue-800';
        textColorDark = 'dark:text-blue-400';
        break;
      case 'vip':
        bgColorLight = 'bg-purple-100';
        bgColorDark = 'dark:bg-purple-900/30';
        textColorLight = 'text-purple-800';
        textColorDark = 'dark:text-purple-400';
        break;
      case 'royal':
        bgColorLight = 'bg-amber-100';
        bgColorDark = 'dark:bg-amber-900/30';
        textColorLight = 'text-amber-800';
        textColorDark = 'dark:text-amber-400';
        break;
      default:
        bgColorLight = 'bg-gray-100';
        bgColorDark = 'dark:bg-gray-800';
        textColorLight = 'text-gray-800';
        textColorDark = 'dark:text-gray-300';
    }
    
    return (
      <span className={`inline-flex items-center px-2.5 py-1.5 rounded-full text-sm font-medium ${bgColorLight} ${bgColorDark} ${textColorLight} ${textColorDark}`}>
        <FaCrown className="mr-1" />
        {type.charAt(0).toUpperCase() + type.slice(1)}
      </span>
    );
  };

  const renderTimeline = (code) => {
    return (
      <div className="mt-4">
        <div className="mb-4 p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <h4 className="text-sm font-medium text-gray-600 dark:text-gray-300 mb-2">
            {getLocalizedText('Срок действия промокода', 'Промокодтың жарамдылық мерзімі', 'Promo Code Validity Period')}
          </h4>
          <div className="relative">
            <div className="overflow-hidden h-2 mb-2 text-xs flex rounded bg-gray-200 dark:bg-gray-700">
              <div 
                style={{ 
                  width: calculatePromoTimelinePercent(code.created_at, code.expires_at) + '%' 
                }} 
                className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-amber-500"
              ></div>
            </div>
            <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400">
              <span>{formatDate(code.created_at)}</span>
              <span>{formatDate(code.expires_at)}</span>
            </div>
          </div>
        </div>

        <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <h4 className="text-sm font-medium text-gray-600 dark:text-gray-300 mb-2">
            {getLocalizedText('Длительность подписки', 'Жазылым ұзақтығы', 'Subscription Duration')}
          </h4>
          <div className="flex items-center">
            <FaClock className="mr-2 text-amber-500 dark:text-amber-400" />
            <span className="text-xl font-semibold text-gray-800 dark:text-gray-200">
              {code.duration_days} {getLocalizedText('дней', 'күн', 'days')}
            </span>
          </div>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
            {getLocalizedText(
              'После активации подписка будет действительна в течение этого периода времени.',
              'Белсендіргеннен кейін жазылым осы уақыт ішінде жарамды болады.',
              'After activation, the subscription will be valid for this period of time.'
            )}
          </p>
        </div>
      </div>
    );
  };
  
  const calculatePromoTimelinePercent = (startDate, endDate) => {
    const start = new Date(startDate);
    const end = new Date(endDate);
    const now = new Date();
    
    const totalDuration = end - start;
    const elapsed = now - start;
    
    return Math.min(100, Math.max(0, (elapsed / totalDuration) * 100));
  };

  const renderPromoCodeCard = (code) => {
    const isExpanded = expandedCards[code.code] || false;
    const activeTab = activeTabs[code.code] || 'details';
    
    return (
      <div key={code.code} className="bg-white dark:bg-gray-800 rounded-xl shadow-md overflow-hidden transition-all duration-300 hover:shadow-lg border border-gray-200 dark:border-gray-700">
        {/* Header */}
        <div className="bg-gradient-to-r from-amber-500 to-yellow-600 p-4 flex justify-between items-center">
          <div>
            <span className="text-xs font-semibold text-amber-100 uppercase tracking-wider">
              {t.promoCode || "Promo Code"}
            </span>
            <div className="mt-1 flex items-center">
              <span className="text-xl font-bold text-white">
                {code.code}
              </span>
              <button
                onClick={() => copyToClipboard(code.code)}
                className="ml-2 text-amber-200 hover:text-white p-1 rounded-full hover:bg-amber-500/30"
                title={t.copy || "Copy"}
              >
                <FaCopy size={16} />
              </button>
            </div>
          </div>
          <div className="flex flex-col items-end">
            {renderStatusBadge(code.status)}
          </div>
        </div>
        
        {/* Top info panel */}
        <div className="p-4 bg-gray-50 dark:bg-gray-800/40 border-b border-gray-200 dark:border-gray-700">
          <div className="flex flex-wrap justify-between items-center gap-2">
            <div>
              {renderSubscriptionBadge(code.subscription_type)}
            </div>
            <div className="flex items-center">
              <span className="flex items-center text-sm text-gray-600 dark:text-gray-300">
                <FaCalendarAlt className="mr-1" />
                {getLocalizedText('до', 'дейін', 'until')} {formatDate(code.expires_at)}
              </span>
              <button 
                onClick={() => toggleExpand(code.code)}
                className="ml-3 p-1 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-300 dark:hover:bg-gray-600"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className={`h-5 w-5 transition-transform duration-200 ${isExpanded ? 'transform rotate-180' : ''}`} viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          </div>
          
          {/* Quick stats */}
          <div className="mt-3 grid grid-cols-2 gap-2">
            <div className="flex flex-col p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
              <span className="text-xs text-gray-500 dark:text-gray-400">{getLocalizedText('Длительность подписки', 'Жазылым ұзақтығы', 'Subscription Duration')}</span>
              <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{code.duration_days} {getLocalizedText('дней', 'күн', 'days')}</span>
            </div>
            <div className="flex flex-col p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
              <span className="text-xs text-gray-500 dark:text-gray-400">{getLocalizedText('Использования', 'Қолдану', 'Uses')}</span>
              <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
                {code.usage_count !== undefined ? `${code.usage_count} / ${code.usage_limit || 1}` : '-'}
              </span>
            </div>
          </div>
        </div>
        
        {isExpanded && (
          <>
            {/* Tabs */}
            <div className="flex border-b border-gray-200 dark:border-gray-700">
              <button
                className={`flex-1 py-3 px-4 text-sm font-medium ${activeTab === 'details' 
                  ? 'text-amber-600 dark:text-amber-400 border-b-2 border-amber-600 dark:border-amber-400 bg-amber-50 dark:bg-amber-900/10' 
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}`}
                onClick={() => changeTab(code.code, 'details')}
              >
                <span className="flex items-center justify-center">
                  <FaInfoCircle className="mr-1" />
                  {getLocalizedText('Детали', 'Мәліметтер', 'Details')}
                </span>
              </button>
              <button
                className={`flex-1 py-3 px-4 text-sm font-medium ${activeTab === 'timeline' 
                  ? 'text-amber-600 dark:text-amber-400 border-b-2 border-amber-600 dark:border-amber-400 bg-amber-50 dark:bg-amber-900/10' 
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}`}
                onClick={() => changeTab(code.code, 'timeline')}
              >
                <span className="flex items-center justify-center">
                  <FaClock className="mr-1" />
                  {getLocalizedText('Таймлайн', 'Таймлайн', 'Timeline')}
                </span>
              </button>
            </div>
            
            {/* Tab content */}
            <div className="p-4">
              {activeTab === 'details' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="flex flex-col space-y-1">
                    <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{getLocalizedText('Код', 'Код', 'Code')}</span>
                    <span className="text-sm text-gray-800 dark:text-gray-200 break-all">{code.code}</span>
                  </div>
                  <div className="flex flex-col space-y-1">
                    <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{getLocalizedText('Создан', 'Құрылды', 'Created')}</span>
                    <span className="text-sm text-gray-800 dark:text-gray-200">{formatDateTime(code.created_at)}</span>
                  </div>
                  <div className="flex flex-col space-y-1">
                    <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{getLocalizedText('Действует до', 'Мерзімі', 'Valid Until')}</span>
                    <span className="text-sm text-gray-800 dark:text-gray-200">{formatDateTime(code.expires_at)}</span>
                  </div>
                  <div className="flex flex-col space-y-1">
                    <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{getLocalizedText('Тип подписки', 'Жазылым түрі', 'Subscription Type')}</span>
                    <span className="text-sm text-gray-800 dark:text-gray-200 capitalize">{code.subscription_type}</span>
                  </div>
                  {code.usage_limit !== undefined && (
                    <>
                      <div className="flex flex-col space-y-1">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{getLocalizedText('Лимит использований', 'Пайдалану шегі', 'Usage Limit')}</span>
                        <span className="text-sm text-gray-800 dark:text-gray-200">{code.usage_limit}</span>
                      </div>
                      <div className="flex flex-col space-y-1">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{getLocalizedText('Текущие использования', 'Ағымдағы пайдалану', 'Current Usage')}</span>
                        <span className="text-sm text-gray-800 dark:text-gray-200">{code.usage_count}</span>
                      </div>
                    </>
                  )}
                  
                  <div className="md:col-span-2 flex flex-col space-y-1">
                    <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{getLocalizedText('Статус', 'Мәртебе', 'Status')}</span>
                    <div className="flex items-center">
                      {renderStatusBadge(code.status)}
                      <span className="ml-2 text-sm text-gray-600 dark:text-gray-400">
                        {getActiveStatusDescription(code.status)}
                      </span>
                    </div>
                  </div>
                  
                  {/* User information section - Move from Users tab to Details tab */}
                  <div className="md:col-span-2 mt-4">
                    <h4 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-3">
                      {getLocalizedText('Использован', 'Пайдаланушы', 'Used By')}
                    </h4>
                    
                    {!code.used_by_info || code.used_by_info.length === 0 ? (
                      <div>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                          {getLocalizedText('Этот код еще никто не использовал', 'Бұл кодты әлі ешкім пайдаланбаған', 'No users have used this code yet')}
                        </p>
                        <div className="flex items-center p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-dashed border-gray-300 dark:border-gray-700">
                          <div className="flex items-center justify-center h-10 w-10 rounded-full bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400">
                            <FaUser />
                          </div>
                          <div className="ml-3">
                            <p className="text-sm font-medium text-gray-400 dark:text-gray-500">
                              {t.futureName || "ФИО пользователя"}
                            </p>
                            <p className="text-xs text-gray-400 dark:text-gray-500">
                              IIN: {t.futureIIN || "000000000000"}
                            </p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {code.used_by_info.map((user, index) => (
                          <div key={index} className="flex items-center p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                            <div className="flex items-center justify-center h-10 w-10 rounded-full bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400">
                              <FaUser />
                            </div>
                            <div className="ml-3">
                              <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
                                {user.full_name || t.anonymousUser || "Анонимный пользователь"}
                              </p>
                              <p className="text-xs text-gray-500 dark:text-gray-400">
                                IIN: {user.iin || '-'}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {activeTab === 'timeline' && (
                <div>
                  {renderTimeline(code)}
                  
                  <div className="mt-6">
                    <h4 className="text-sm font-medium text-gray-600 dark:text-gray-300 mb-3">
                      {getLocalizedText('События', 'Оқиғалар', 'Events')}
                    </h4>
                    <div className="space-y-4">
                      <div className="flex">
                        <div className="flex-shrink-0">
                          <div className="flex items-center justify-center h-8 w-8 rounded-full bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
                            <FaTag />
                          </div>
                        </div>
                        <div className="ml-4">
                          <h5 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                            {getLocalizedText('Код создан', 'Код жасалды', 'Code Created')}
                          </h5>
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            {formatDateTime(code.created_at)}
                          </p>
                        </div>
                      </div>
                      
                      {code.usage_count > 0 && (
                        <div className="flex">
                          <div className="flex-shrink-0">
                            <div className="flex items-center justify-center h-8 w-8 rounded-full bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400">
                              <FaUser />
                            </div>
                          </div>
                          <div className="ml-4">
                            <h5 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                              {getLocalizedText('Код использован', 'Код пайдаланылды', 'Code Used')}
                            </h5>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                              {code.usage_count} {code.usage_count === 1 
                                ? getLocalizedText('раз', 'рет', 'time used') 
                                : getLocalizedText('раз', 'рет', 'times used')}
                            </p>
                          </div>
                        </div>
                      )}
                      
                      {new Date(code.expires_at) < new Date() && (
                        <div className="flex">
                          <div className="flex-shrink-0">
                            <div className="flex items-center justify-center h-8 w-8 rounded-full bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400">
                              <FaBan />
                            </div>
                          </div>
                          <div className="ml-4">
                            <h5 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                              {getLocalizedText('Срок действия истек', 'Мерзімі өтті', 'Code Expired')}
                            </h5>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                              {formatDateTime(code.expires_at)}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    );
  };

  return (
    <div className="p-4 md:p-6 bg-white dark:bg-gray-900 rounded-lg min-h-screen">
      <h1 className="text-2xl md:text-3xl font-bold mb-6 text-gray-800 dark:text-white">{getLocalizedText('Промокоды', 'Промокодтар', 'Promo Codes')}</h1>
      
      {/* Created Promo Codes */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-800 dark:text-white">{getLocalizedText('Мои промокоды', 'Менің промокодтарым', 'My Promo Codes')}</h2>
          <span className="bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 text-xs font-medium px-2.5 py-1 rounded-full">
            {createdPromoCodes.length} {getLocalizedText('промокодов', 'промокод', 'codes')}
          </span>
        </div>
        
        {loading ? (
          <div className="flex flex-col items-center justify-center py-12 bg-gray-50 dark:bg-gray-800/50 rounded-xl">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-indigo-500"></div>
            <p className="mt-4 text-gray-600 dark:text-gray-400">{t.loading || "Loading..."}</p>
          </div>
        ) : createdPromoCodes.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 bg-gray-50 dark:bg-gray-800/50 rounded-xl text-center">
            <FaInfoCircle className="h-12 w-12 text-gray-400 dark:text-gray-500 mb-4" />
            <h3 className="text-lg font-medium text-gray-800 dark:text-white mb-1">{t.noPromoCodesTitle || "No Promo Codes"}</h3>
            <p className="text-gray-600 dark:text-gray-400 max-w-md">{t.noPromoCodes || "You don't have any promo codes yet"}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6">
            {createdPromoCodes.map(renderPromoCodeCard)}
          </div>
        )}
      </div>
      
      {/* Used Promo Codes */}
      {usedPromoCodes.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-800 dark:text-white">{t.usedPromoCodes || "Used Promo Codes"}</h2>
            <span className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400 text-xs font-medium px-2.5 py-1 rounded-full">
              {usedPromoCodes.length} {t.codesTotal || "codes"}
            </span>
          </div>
          
          <div className="grid grid-cols-1 gap-6">
            {usedPromoCodes.map(renderPromoCodeCard)}
          </div>
        </div>
      )}
      
      {/* Guide */}
      <div className="mt-12 bg-gradient-to-r from-amber-50 to-yellow-50 dark:from-amber-900/10 dark:to-yellow-900/10 rounded-xl p-6 border border-amber-100 dark:border-amber-800/20">
        <h2 className="text-lg font-semibold text-gray-800 dark:text-white mb-4">
          {getLocalizedText('Руководство по промокодам', 'Промокодтар нұсқаулығы', 'Promo Code Guide')}
        </h2>
        <div className="grid grid-cols-1 gap-4">
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-amber-100 dark:border-amber-800/20">
            <div className="flex items-center text-amber-600 dark:text-amber-400 mb-3">
              <FaInfoCircle className="mr-2" />
              <h3 className="font-medium">{getLocalizedText('Как использовать промокоды', 'Промокодтарды қалай пайдалану керек', 'How to Use Promo Codes')}</h3>
            </div>
            <div className="space-y-3 text-sm text-gray-600 dark:text-gray-400">
              <p>
                <span className="font-medium text-gray-700 dark:text-gray-300">{getLocalizedText('Шаг 1:', '1-қадам:', 'Step 1:')}</span>{" "}
                {getLocalizedText(
                  'Зарегистрируйтесь на нашей платформе, если у вас еще нет аккаунта.',
                  'Егер сізде аккаунт жоқ болса, платформамызда тіркеліңіз.',
                  'Register on our platform if you haven\'t already.'
                )}
              </p>
              <p>
                <span className="font-medium text-gray-700 dark:text-gray-300">{getLocalizedText('Шаг 2:', '2-қадам:', 'Step 2:')}</span>{" "}
                {getLocalizedText(
                  'Перейдите в раздел подписки и введите промокод.',
                  'Жазылым бөліміне өтіп, промокодты енгізіңіз.',
                  'Go to the subscription section and enter the promo code.'
                )}
              </p>
              <p>
                <span className="font-medium text-gray-700 dark:text-gray-300">{getLocalizedText('Шаг 3:', '3-қадам:', 'Step 3:')}</span>{" "}
                {getLocalizedText(
                  'Активируйте код, чтобы сразу получить подписку.',
                  'Жазылымды бірден алу үшін кодты іске қосыңыз.',
                  'Activate the code to receive your subscription immediately.'
                )}
              </p>
            </div>
          </div>
          
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-amber-100 dark:border-amber-800/20">
            <div className="flex items-center text-amber-600 dark:text-amber-400 mb-2">
              <FaUser className="mr-2" />
              <h3 className="font-medium">{getLocalizedText('Информация об активации', 'Белсендіру туралы ақпарат', 'Activation Information')}</h3>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {getLocalizedText(
                'Когда кто-то активирует ваш промокод, вы увидите информацию о них в деталях промокода. Вы сможете отслеживать, кто использовал ваши рефералы.',
                'Біреу сіздің промокодыңызды белсендіргенде, сіз олардың деректерін промокод мәліметтерінде көресіз. Рефералдарыңызды кім пайдаланғанын бақылай аласыз.',
                'When someone activates your promo code, you\'ll see their information in the promo code details. You\'ll be able to track who has used your referrals.'
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PromoCodesPage; 