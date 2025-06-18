import React, { useState, useEffect } from 'react';
import { useLanguage } from '../../contexts/LanguageContext';
import { translations } from '../../translations/translations';
import { useTheme } from '../../contexts/ThemeContext';
import { useNavigate } from 'react-router-dom';
import api from '../../utils/axios';

// Icons
import { 
  MdDirectionsBike, 
  MdDirectionsCar, 
  MdLocalShipping, 
  MdPersonAdd, 
  MdTimer, 
  MdInfo, 
  MdStar,
  MdTrendingUp,
  MdSchool,
  MdSpeed
} from 'react-icons/md';
import { 
  FaTruck, 
  FaTruckMoving, 
  FaBusAlt, 
  FaLock, 
  FaInfoCircle, 
  FaCrown, 
  FaRocket, 
  FaTrophy, 
  FaArrowRight, 
  FaExclamationCircle, 
  FaTimes, 
  FaCheck, 
  FaPlay, 
  FaClock, 
  FaStar,
  FaUsers,
  FaGamepad,
  FaChartLine,
  FaGraduationCap,
  FaFire,
  FaShieldAlt
} from 'react-icons/fa';
import './test-dashboard.css';
import TestModal from '../../components/TestModal';

const TestDashboardPage = () => {
  const { language } = useLanguage();
  const t = translations[language];
  const { isDark } = useTheme();
  const navigate = useNavigate();
  
  const [activeTab, setActiveTab] = useState('single');
  const [subscription, setSubscription] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const [lobbyCode, setLobbyCode] = useState('');
  const [animateEntry, setAnimateEntry] = useState(false);
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(null);
  
  // Active lobby state
  const [activeLobby, setActiveLobby] = useState(null);
  const [remainingTime, setRemainingTime] = useState(0);
  const [isLoadingLobby, setIsLoadingLobby] = useState(false);

  // Categories stats state
  const [categoriesStats, setCategoriesStats] = useState(null);
  const [totalQuestions, setTotalQuestions] = useState(0);

  // Enable entry animations after initial render
  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimateEntry(true);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  // Update theme class on body element for better compatibility
  useEffect(() => {
    if (isDark) {
      document.body.classList.add('dark');
      document.body.classList.remove('light');
    } else {
      document.body.classList.add('light');
      document.body.classList.remove('dark');
    }
    
    return () => {
      document.body.classList.remove('dark', 'light');
    };
  }, [isDark]);

  // Timer effect for active lobby countdown
  useEffect(() => {
    let interval = null;
    if (activeLobby && activeLobby.remaining_seconds > 0) {
      interval = setInterval(() => {
        setRemainingTime(prevTime => {
          if (prevTime <= 1) {
            clearInterval(interval);
            // When time expires, refresh to check if lobby is still active
            checkActiveLobby();
            return 0;
          }
          return prevTime - 1;
        });
      }, 1000);
    }
    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [activeLobby]);

  // Format time from seconds to HH:MM:SS
  const formatTime = (totalSeconds) => {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  // Check if user has an active lobby
  const checkActiveLobby = async () => {
    try {
      setIsLoadingLobby(true);
      console.log("Checking for active lobby");
      const response = await api.get('/lobbies/active-lobby');
      
      console.log("Active lobby check response:", response.data);
      console.log("Response data object:", JSON.stringify(response.data.data, null, 2));
      
      if (response.data.status === "ok") {
        const lobbyData = response.data.data;
        console.log("Lobby data has_active_lobby:", lobbyData.has_active_lobby);
        console.log("Full lobby data:", lobbyData);
        
        if (lobbyData.has_active_lobby) {
          console.log("Active lobby found:", lobbyData);
          setActiveLobby(lobbyData);
          setRemainingTime(lobbyData.remaining_seconds || 0);
        } else {
          console.log("No active lobby");
          setActiveLobby(null);
          setRemainingTime(0);
        }
      } else {
        console.error("Error checking active lobby:", response.data);
        setErrorMessage(response.data.message || t['failedToCheckActiveLobby'] || 'Failed to check for active lobbies');
      }
    } catch (error) {
      console.error('Error checking for active lobby:', error);
      console.error('Error response:', error.response?.data);
      setErrorMessage(error.response?.data?.message || t['failedToCheckActiveLobby'] || 'Failed to check for active lobbies');
    } finally {
      setIsLoadingLobby(false);
    }
  };

  // Test categories with their permissions - now dynamic
  const getTestCategories = () => {
    if (!categoriesStats) {
      // Fallback to static data while loading
      return [
        {
          id: 'cat1',
          title: 'A1, A, B1',
          description: t['test.motorcycle_license'] || 'Motorcycle License',
          icon: <MdDirectionsBike size={28} />,
          allowedPlans: ['economy', 'vip', 'royal', 'school'],
          questions: 0,
          level: t['level.beginner'] || 'Beginner',
          color: 'emerald',
          difficulty: 1,
        },
        {
          id: 'cat2',
          title: 'B, BE',
          description: t['test.car_license'] || 'Car License',
          icon: <MdDirectionsCar size={28} />,
          allowedPlans: ['economy', 'vip', 'royal', 'school'],
          questions: 0,
          level: t['level.beginner'] || 'Beginner',
          popular: true,
          color: 'golden',
          difficulty: 1,
        },
        {
          id: 'cat3',
          title: 'C, C1',
          description: t['test.truck_license'] || 'Truck License',
          icon: <FaTruck size={28} />,
          allowedPlans: ['vip', 'royal', 'school'],
          questions: 0,
          level: t['level.intermediate'] || 'Intermediate',
          color: 'amber',
          difficulty: 2,
        },
        {
          id: 'cat4',
          title: 'BC1',
          description: t['test.commercial_license'] || 'Commercial License',
          icon: <FaTruckMoving size={28} />,
          allowedPlans: ['vip', 'royal', 'school'],
          questions: 0,
          level: t['level.intermediate'] || 'Intermediate',
          color: 'orange',
          difficulty: 2,
        },
        {
          id: 'cat5',
          title: 'D1, D, Tb',
          description: t['test.bus_license'] || 'Bus License',
          icon: <FaBusAlt size={28} />,
          allowedPlans: ['vip', 'royal', 'school'],
          questions: 0,
          level: t['level.advanced'] || 'Advanced',
          color: 'amber',
          difficulty: 3,
        },
        {
          id: 'cat6',
          title: 'C1, CE, D1, DE',
          description: t['test.heavy_vehicle_license'] || 'Heavy Vehicle License',
          icon: <MdLocalShipping size={28} />,
          allowedPlans: ['vip', 'royal', 'school'],
          questions: 0,
          level: t['level.advanced'] || 'Advanced',
          color: 'red',
          difficulty: 3,
        },
        {
          id: 'cat7',
          title: 'Tm',
          description: t['test.tram_license'] || 'Tram License',
          icon: <MdTimer size={28} />,
          allowedPlans: ['vip', 'royal', 'school'],
          questions: 0,
          level: t['level.advanced'] || 'Advanced',
          color: 'orange',
          difficulty: 3,
        }
      ];
    }

    // Map API data to UI format
    const categoryMapping = {
      'cat1': {
        description: t['test.motorcycle_license'] || 'Motorcycle License',
        icon: <MdDirectionsBike size={28} />,
        allowedPlans: ['economy', 'vip', 'royal', 'school'],
        level: t['level.beginner'] || 'Beginner',
        color: 'emerald',
        difficulty: 1,
      },
      'cat2': {
        description: t['test.car_license'] || 'Car License',
        icon: <MdDirectionsCar size={28} />,
        allowedPlans: ['economy', 'vip', 'royal', 'school'],
        level: t['level.beginner'] || 'Beginner',
        popular: true,
        color: 'golden',
        difficulty: 1,
      },
      'cat3': {
        description: t['test.truck_license'] || 'Truck License',
        icon: <FaTruck size={28} />,
        allowedPlans: ['vip', 'royal', 'school'],
        level: t['level.intermediate'] || 'Intermediate',
        color: 'amber',
        difficulty: 2,
      },
      'cat4': {
        description: t['test.commercial_license'] || 'Commercial License',
        icon: <FaTruckMoving size={28} />,
        allowedPlans: ['vip', 'royal', 'school'],
        level: t['level.intermediate'] || 'Intermediate',
        color: 'orange',
        difficulty: 2,
      },
      'cat5': {
        description: t['test.bus_license'] || 'Bus License',
        icon: <FaBusAlt size={28} />,
        allowedPlans: ['vip', 'royal', 'school'],
        level: t['level.advanced'] || 'Advanced',
        color: 'amber',
        difficulty: 3,
      },
      'cat6': {
        description: t['test.heavy_vehicle_license'] || 'Heavy Vehicle License',
        icon: <MdLocalShipping size={28} />,
        allowedPlans: ['vip', 'royal', 'school'],
        level: t['level.advanced'] || 'Advanced',
        color: 'red',
        difficulty: 3,
      },
      'cat7': {
        description: t['test.tram_license'] || 'Tram License',
        icon: <MdTimer size={28} />,
        allowedPlans: ['vip', 'royal', 'school'],
        level: t['level.advanced'] || 'Advanced',
        color: 'orange',
        difficulty: 3,
      }
    };

    return categoriesStats.categories.map(categoryData => {
      const mapping = categoryMapping[categoryData.id];
      return {
        id: categoryData.id,
        title: categoryData.title,
        categories: categoryData.categories,
        breakdown: categoryData.breakdown,
        description: mapping.description,
        icon: mapping.icon,
        allowedPlans: mapping.allowedPlans,
        questions: categoryData.total_questions,
        level: mapping.level,
        popular: mapping.popular,
        color: mapping.color,
        difficulty: mapping.difficulty,
      };
    });
  };

  // Fetch categories statistics
  const fetchCategoriesStats = async () => {
    try {
      console.log("Fetching categories statistics");
      const response = await api.get('/lobbies/categories/stats');
      
      if (response.data.status === "ok") {
        const statsData = response.data.data;
        console.log("Categories stats received:", statsData);
        setCategoriesStats(statsData);
        setTotalQuestions(statsData.total_questions);
      } else {
        console.error("Error in categories stats response:", response.data);
        setErrorMessage(response.data.message || t['failedToLoadCategories'] || 'Failed to load categories data');
      }
    } catch (error) {
      console.error('Error fetching categories stats:', error);
      setErrorMessage(error.response?.data?.message || t['failedToLoadCategories'] || 'Failed to load categories data');
    }
  };

  // Fetch user subscription and active lobby on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        
        // Fetch subscription data
        const response = await api.get('/users/my/subscription');
        
        if (response.data.status === "ok") {
          const subData = response.data.data;
          if (subData.has_subscription) {
            setSubscription({
              subscription_type: subData.subscription_type,
              expires_at: subData.expires_at,
              days_left: subData.days_left,
              duration_days: subData.duration_days
            });
          } else {
            setSubscription(null);
          }
        } else {
          console.error("Error in subscription response:", response.data);
          setErrorMessage(response.data.message || t['failedToLoadSubscription'] || 'Failed to load subscription data');
        }
        
        // Fetch categories statistics
        await fetchCategoriesStats();
        
        // Check for active test lobby
        await checkActiveLobby();
        
      } catch (error) {
        console.error('Error fetching data:', error);
        setErrorMessage(error.response?.data?.message || t['failedToConnect'] || 'Failed to connect to server');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [t]);

  // Test categories with their permissions
  const testCategories = getTestCategories();

  // Check if category is available based on subscription
  const isCategoryAvailable = (category) => {
    if (!subscription || !subscription.subscription_type) {
      return false;
    }
    return category.allowedPlans.includes(subscription.subscription_type.toLowerCase());
  };

  // Get subscription tier info
  const getSubscriptionTier = () => {
    if (!subscription) return { name: 'Free', icon: null, color: 'gray' };
    
    const type = subscription.subscription_type?.toLowerCase();
    switch(type) {
      case 'economy':
        return { name: 'Economy', icon: <MdSchool />, color: 'emerald' };
      case 'vip':
        return { name: 'VIP', icon: <FaStar />, color: 'purple' };
      case 'royal':
        return { name: 'Royal', icon: <FaCrown />, color: 'amber' };
      case 'school':
        return { name: 'School', icon: <FaGraduationCap />, color: 'golden' };
      default:
        return { name: 'Free', icon: null, color: 'gray' };
    }
  };

  // Handler for starting a test
  const handleStartTest = (category) => {
    console.log('handleStartTest called with category:', category);
    
    // Check if there's an active test first
    if (activeLobby) {
      console.log('Active lobby detected, showing alert');
      // Show message that user should continue or finish active test
      alert(t['test.hasActiveTest'] || 'You have an active test. Please continue or finish it before starting a new one.');
      return;
    }
    
    console.log('Setting selected category and opening modal');
    setSelectedCategory(category);
    setTestModalOpen(true);
    // Prevent scrolling when modal is open
    document.body.classList.add('modal-open');
    console.log('Modal should be open now, testModalOpen:', true);
  };

  // Update the modal close handling to remove the class
  const handleCloseModal = () => {
    setTestModalOpen(false);
    document.body.classList.remove('modal-open');
  };

  // Handler for continuing an active test
  const handleContinueTest = () => {
    if (activeLobby && activeLobby.lobby_id) {
      // Check if it's a multiplayer lobby
      if (activeLobby.mode === 'multiplayer') {
        console.log(`Continuing multiplayer test in lobby: ${activeLobby.lobby_id}, redirecting to /multiplayer/test/${activeLobby.lobby_id}`);
        navigate(`/multiplayer/test/${activeLobby.lobby_id}`);
      } else {
        // Solo mode
        console.log(`Continuing solo test in lobby: ${activeLobby.lobby_id}, redirecting to /test/${activeLobby.lobby_id}`);
        navigate(`/test/${activeLobby.lobby_id}`);
      }
    } else {
      console.error('No active lobby to continue');
      setErrorMessage(t['noActiveLobby'] || "No active test found");
    }
  };

  // Handler for creating a lobby
  const handleCreateLobby = () => {
    console.log('handleCreateLobby called');
    console.log('activeLobby:', activeLobby);
    console.log('subscription:', subscription);
    
    // Check if there's an active test first
    if (activeLobby) {
      console.log('Active lobby detected, showing alert');
      // Show message that user should continue or finish active test
      alert(t['test.hasActiveTest'] || 'You have an active test. Please continue or finish it before starting a new one.');
      return;
    }
    
    // Check if user has Royal or School subscription
    if (!subscription || !['royal', 'school'].includes(subscription.subscription_type?.toLowerCase())) {
      console.log('Subscription check failed:', subscription?.subscription_type);
      alert(t['test.needRoyalOrSchoolForMultiplayer'] || 'You need Royal or School subscription to create multiplayer lobbies.');
      return;
    }
    
    console.log('All checks passed, navigating to create lobby page');
    navigate('/multiplayer/create');
  };

  // Handler for joining a lobby
  const handleJoinLobby = () => {
    console.log('handleJoinLobby called');
    console.log('activeLobby:', activeLobby);
    console.log('lobbyCode:', lobbyCode);
    
    // Check if there's an active test first
    if (activeLobby) {
      console.log('Active lobby detected, showing alert');
      // Show message that user should continue or finish active test
      alert(t['test.hasActiveTest'] || 'You have an active test. Please continue or finish it before starting a new one.');
      return;
    }
    
    if (!lobbyCode.trim()) {
      console.log('Lobby code is empty');
      alert(t['test.enterLobbyCode'] || 'Please enter a lobby code');
      return;
    }
    
    console.log('All checks passed, joining lobby with code:', lobbyCode);
    navigate(`/multiplayer/join/${lobbyCode.trim()}`);
  };

  const subscriptionTier = getSubscriptionTier();

  // Debug logging
  console.log('TestDashboardPage render - subscription:', subscription);
  console.log('TestDashboardPage render - subscriptionTier:', subscriptionTier);
  console.log('TestDashboardPage render - activeTab:', activeTab);

  return (
    <div className={`test-dashboard ${animateEntry ? 'animate-entry' : ''} ${isDark ? 'dark-theme' : ''}`}>
      {/* Hero Section */}
      <div className="hero-section">
        <div className="hero-content">
          <div className="hero-text">
            <h1 className="hero-title">
              <span className="title-main">{t['test.title'] || 'Категории тестов'}</span>
              <span className="title-subtitle">{t['test.subtitle'] || 'Выберите категорию для начала обучения'}</span>
            </h1>
            <p className="hero-description">
              {t['test.hero_description'] || 'Подготовьтесь к экзамену с официальными вопросами и современными методами обучения'}
            </p>
            {totalQuestions > 0 && (
              <div className="total-questions-info">
                <MdInfo className="info-icon" />
                <span>{t['total_questions'] || 'Всего вопросов'}: <strong>{totalQuestions}</strong></span>
              </div>
            )}
          </div>
          
          <div className="subscription-card">
            <div className="subscription-header">
              <div className={`subscription-badge tier-${subscriptionTier.color}`}>
                {subscriptionTier.icon}
                <span>{subscriptionTier.name}</span>
              </div>
              {subscription && (
                <div className="days-remaining">
                  <FaClock className="clock-icon" />
                  <span>{subscription.days_left} {t['daysLeft'] || 'дней'}</span>
                </div>
              )}
            </div>
            
            {!subscription && (
              <div className="upgrade-prompt">
                <FaExclamationCircle className="warning-icon" />
                <span>{t['subscriptionBenefits'] || 'Активируйте подписку для доступа ко всем функциям'}</span>
                <button className="upgrade-btn">
                  <FaRocket />
                  {t['upgrade'] || 'Обновить'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Active Test Alert */}
      {activeLobby && (
        <div className="active-test-alert">
          <div className="alert-icon">
            <FaPlay />
          </div>
          <div className="alert-content">
            <h3>{t['test.activeTestAvailable'] || 'У вас есть активный тест'}</h3>
            <p>{t['test.activeTestMessage'] || 'Продолжите с того места, где остановились'}</p>
            <div className="time-display">
              <FaClock />
              <span>{formatTime(remainingTime)}</span>
            </div>
          </div>
          <button className="continue-btn" onClick={handleContinueTest}>
            <FaPlay />
            {t['test.continueTest'] || 'Продолжить'}
          </button>
        </div>
      )}

      {/* Mode Selection */}
      <div className="mode-selection">
        <div className="mode-tabs">
          <button
            className={`mode-tab ${activeTab === 'single' ? 'active' : ''}`}
            onClick={() => setActiveTab('single')}
          >
            <FaGraduationCap className="tab-icon" />
            <span>{t['test.single_mode'] || 'Одиночный режим'}</span>
            <span className="tab-description">{t['test.single_description_short'] || 'Индивидуальная практика'}</span>
          </button>
          
          <button
            className={`mode-tab ${activeTab === 'multiplayer' ? 'active' : ''}`}
            onClick={() => setActiveTab('multiplayer')}
          >
            <FaUsers className="tab-icon" />
            <span>{t['test.multiplayer_mode'] || 'Мультиплеер'}</span>
            <span className="tab-description">{t['test.multiplayer_description_short'] || 'Соревнования в реальном времени'}</span>
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="loading-container">
          <div className="loading-spinner">
            <div className="spinner"></div>
          </div>
          <p className="loading-text">{t['loading'] || 'Загрузка...'}</p>
        </div>
      ) : errorMessage ? (
        <div className="error-container">
          <FaExclamationCircle className="error-icon" />
          <span>{errorMessage}</span>
        </div>
      ) : (
        <div className="content-section">
          {activeTab === 'single' ? (
            <div className="single-mode-content">
              <div className="section-header">
                <h2>{t['test.choose_category'] || 'Выберите категорию'}</h2>
                <p>{t['test.single_description'] || 'Практикуйтесь с официальными экзаменационными вопросами для каждой категории'}</p>
              </div>
              
              <div className="categories-grid">
                {testCategories.map((category, index) => (
                  <div 
                    key={category.id}
                    className={`category-card ${!isCategoryAvailable(category) ? 'locked' : ''} ${category.popular ? 'popular' : ''}`}
                    onClick={() => isCategoryAvailable(category) && handleStartTest(category)}
                    style={{animationDelay: `${index * 0.1}s`}}
                  >
                    {category.popular && (
                      <div className="popular-badge">
                        <FaFire />
                        <span>{t['popular'] || 'Популярное'}</span>
                      </div>
                    )}
                    
                    <div className={`category-icon color-${category.color}`}>
                      {category.icon}
                    </div>
                    
                    <div className="category-info">
                      <h3 className="category-title">{category.title}</h3>
                      <p className="category-description">{category.description}</p>
                      
                      <div className="category-meta">
                        <div className={`difficulty-badge difficulty-${category.difficulty}`}>
                          {Array.from({ length: category.difficulty }, (_, i) => (
                            <FaStar key={i} />
                          ))}
                          <span>{category.level}</span>
                        </div>
                        
                        <div className="questions-count">
                          <MdSpeed />
                          <span>{category.questions} {t['questions'] || 'вопросов'}</span>
                        </div>
                      </div>
                    </div>
                    
                    {isCategoryAvailable(category) ? (
                      <button 
                        className="start-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStartTest(category);
                        }}
                      >
                        <span>{t['startTest'] || 'Начать тест'}</span>
                        <FaArrowRight />
                      </button>
                    ) : (
                      <div className="lock-overlay">
                        <FaLock />
                        <span>{t['test.upgrade_required'] || 'Требуется подписка'}</span>
                        <button className="unlock-btn">
                          {t['upgrade'] || 'Обновить'}
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="multiplayer-content">
              <div className="section-header">
                <h2>{t['test.multiplayer_title'] || 'Мультиплеер режим'}</h2>
                <p>{t['test.multiplayer_description'] || 'Соревнуйтесь с друзьями и другими пользователями'}</p>
              </div>
              
              <div className="multiplayer-options">
                <div className="multiplayer-card join-card">
                  <div className="card-header">
                    <div className="card-icon join-icon">
                      <FaGamepad />
                    </div>
                    <h3>{t['test.join_lobby'] || 'Присоединиться'}</h3>
                    <p>{t['test.join_description'] || 'Введите код лобби для участия'}</p>
                  </div>
                  
                  <div className="join-form">
                    <div className="input-group">
                      <input
                        type="text"
                        value={lobbyCode}
                        onChange={(e) => setLobbyCode(e.target.value)}
                        placeholder={t['test.enter_lobby_code'] || 'Код лобби'}
                        className="lobby-input"
                      />
                      <button 
                        className="join-btn"
                        onClick={handleJoinLobby}
                        disabled={!lobbyCode.trim()}
                      >
                        <FaArrowRight />
                      </button>
                    </div>
                  </div>
                </div>
                
                <div className="multiplayer-card create-card">
                  <div className="card-header">
                    <div className="card-icon create-icon">
                      <FaRocket />
                    </div>
                    <div className="header-content">
                      <h3>{t['test.create_lobby'] || 'Создать лобби'}</h3>
                      {(!subscription || !['royal', 'school'].includes(subscription.subscription_type?.toLowerCase())) && (
                        <div className="premium-tag">
                          <FaCrown />
                          <span>Royal</span>
                        </div>
                      )}
                    </div>
                    <p>{t['test.create_description'] || 'Создайте собственное лобби'}</p>
                  </div>
                  
                  <div className="features-list">
                    <div className="feature-item">
                      <FaChartLine />
                      <span>{t['test.feature_custom'] || 'Настраиваемые параметры'}</span>
                    </div>
                    <div className="feature-item">
                      <FaTrophy />
                      <span>{t['test.feature_leaderboard'] || 'Таблица лидеров'}</span>
                    </div>
                    <div className="feature-item">
                      <FaShieldAlt />
                      <span>{t['test.feature_private'] || 'Приватные комнаты'}</span>
                    </div>
                  </div>
                  
                  <button 
                    className={`create-btn ${!subscription || !['royal', 'school'].includes(subscription.subscription_type?.toLowerCase()) ? 'disabled' : ''}`}
                    onClick={handleCreateLobby}
                    disabled={!subscription || !['royal', 'school'].includes(subscription.subscription_type?.toLowerCase())}
                  >
                    <FaRocket />
                    <span>{t['test.create'] || 'Создать'}</span>
                  </button>
                  
                  {(!subscription || !['royal', 'school'].includes(subscription.subscription_type?.toLowerCase())) && (
                    <div className="upgrade-note">
                      <FaInfoCircle />
                      <span>{t['test.royal_school_only'] || 'Доступно для Royal и School подписок'}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {testModalOpen && (
        <TestModal
          isOpen={testModalOpen}
          onClose={handleCloseModal}
          category={selectedCategory}
          subscription={subscription}
          translations={t}
          isDark={isDark}
        />
      )}
    </div>
  );
};

export default TestDashboardPage; 