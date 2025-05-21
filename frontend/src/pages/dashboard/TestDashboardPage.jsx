import React, { useState, useEffect } from 'react';
import { useLanguage } from '../../contexts/LanguageContext';
import { translations } from '../../translations/translations';
import { useTheme } from '../../contexts/ThemeContext';
import { useNavigate } from 'react-router-dom';
import api from '../../utils/axios';

// Icons
import { MdDirectionsBike, MdDirectionsCar, MdLocalShipping, MdPersonAdd, MdTimer, MdInfo, MdStar } from 'react-icons/md';
import { FaTruck, FaTruckMoving, FaBusAlt, FaLock, FaInfoCircle, FaCrown, FaRocket, FaTrophy, FaArrowRight, FaExclamationCircle, FaTimes, FaCheck, FaPlay, FaClock, FaStar } from 'react-icons/fa';
import './styles.css';
import TestModal from '../../components/TestModal';

const TestDashboardPage = () => {
  const { language } = useLanguage();
  const t = translations[language];
  const { isDarkTheme } = useTheme();
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

  // Enable entry animations after initial render
  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimateEntry(true);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

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
      if (response.data.status === "ok") {
        const lobbyData = response.data.data;
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
  const testCategories = [
    {
      id: 'cat1',
      title: 'A1, A, B1',
      description: t['test.motorcycle_license'] || 'Motorcycle License',
      icon: <MdDirectionsBike size={24} />,
      allowedPlans: ['economy', 'vip', 'royal'],
      questions: 225,
      level: t['level.beginner'] || 'Beginner',
    },
    {
      id: 'cat2',
      title: 'B, BE',
      description: t['test.car_license'] || 'Car License',
      icon: <MdDirectionsCar size={24} />,
      allowedPlans: ['economy', 'vip', 'royal'],
      questions: 350,
      level: t['level.beginner'] || 'Beginner',
      popular: true,
    },
    {
      id: 'cat3',
      title: 'C, C1',
      description: t['test.truck_license'] || 'Truck License',
      icon: <FaTruck size={24} />,
      allowedPlans: ['vip', 'royal'],
      questions: 280,
      level: t['level.intermediate'] || 'Intermediate',
    },
    {
      id: 'cat4',
      title: 'BC1',
      description: t['test.commercial_license'] || 'Commercial License',
      icon: <FaTruckMoving size={24} />,
      allowedPlans: ['vip', 'royal'],
      questions: 310,
      level: t['level.intermediate'] || 'Intermediate',
    },
    {
      id: 'cat5',
      title: 'D1, D, Tb',
      description: t['test.bus_license'] || 'Bus License',
      icon: <FaBusAlt size={24} />,
      allowedPlans: ['vip', 'royal'],
      questions: 290,
      level: t['level.advanced'] || 'Advanced',
    },
    {
      id: 'cat6',
      title: 'C1, CE, D1, DE',
      description: t['test.heavy_vehicle_license'] || 'Heavy Vehicle License',
      icon: <MdLocalShipping size={24} />,
      allowedPlans: ['vip', 'royal'],
      questions: 320,
      level: t['level.advanced'] || 'Advanced',
    },
    {
      id: 'cat7',
      title: 'Tm',
      description: t['test.tram_license'] || 'Tram License',
      icon: <MdTimer size={24} />,
      allowedPlans: ['vip', 'royal'],
      questions: 200,
      level: t['level.advanced'] || 'Advanced',
    }
  ];

  // Check if category is available based on subscription
  const isCategoryAvailable = (category) => {
    if (!subscription || !subscription.subscription_type) {
      return false;
    }
    return category.allowedPlans.includes(subscription.subscription_type.toLowerCase());
  };

  // Level badge color
  const getLevelColor = (level) => {
    const levelKey = level.toLowerCase();
    switch(levelKey) {
      case 'beginner':
      case t['level.beginner']?.toLowerCase():
        return 'level-beginner';
      case 'intermediate':
      case t['level.intermediate']?.toLowerCase():
        return 'level-intermediate';
      case 'advanced':
      case t['level.advanced']?.toLowerCase():
        return 'level-advanced';
      default: return '';
    }
  };

  // Handler for starting a test
  const handleStartTest = (category) => {
    // Check if there's an active test first
    if (activeLobby) {
      // Show message that user should continue or finish active test
      alert(t['test.hasActiveTest'] || 'You have an active test. Please continue or finish it before starting a new one.');
      return;
    }
    
    setSelectedCategory(category);
    setTestModalOpen(true);
    // Prevent scrolling when modal is open
    document.body.classList.add('modal-open');
  };

  // Update the modal close handling to remove the class
  const handleCloseModal = () => {
    setTestModalOpen(false);
    document.body.classList.remove('modal-open');
  };

  // Handler for continuing an active test
  const handleContinueTest = () => {
    if (activeLobby && activeLobby.lobby_id) {
      // Navigate to the test page with the active lobby ID
      console.log(`Continuing test in lobby: ${activeLobby.lobby_id}, redirecting to /test/${activeLobby.lobby_id}`);
      navigate(`/test/${activeLobby.lobby_id}`);
    } else {
      console.error('No active lobby to continue');
      setErrorMessage(t['noActiveLobby'] || "No active test found");
    }
  };

  // Handler for creating a lobby
  const handleCreateLobby = () => {
    // Check if there's an active test first
    if (activeLobby) {
      // Show message that user should continue or finish active test
      alert(t['test.hasActiveTest'] || 'You have an active test. Please continue or finish it before starting a new one.');
      return;
    }
    
    console.log('Creating a lobby');
    // Implement create lobby logic
  };

  // Handler for joining a lobby
  const handleJoinLobby = () => {
    // Check if there's an active test first
    if (activeLobby) {
      // Show message that user should continue or finish active test
      alert(t['test.hasActiveTest'] || 'You have an active test. Please continue or finish it before starting a new one.');
      return;
    }
    
    console.log('Joining lobby with code:', lobbyCode);
    // Implement join lobby logic
  };

  // Render a tooltip
  const renderTooltip = (text, icon = null) => (
    <div className={`tooltip-container ${isDarkTheme ? 'dark-theme' : ''}`}>
      {icon || <MdInfo className="tooltip-icon" />}
      <div className="tooltip-text">{text}</div>
    </div>
  );

  return (
    <div className={`test-dashboard ${isDarkTheme ? 'dark-theme' : ''} ${animateEntry ? 'animate-entry' : ''}`}>
      <div className="dashboard-header">
        <h1 className="dashboard-title">
          {t['test.title'] || 'Категории тестов'}
          {renderTooltip(t['testCategories'] || 'Choose a test category to begin practice')}
        </h1>
        
        <div className="subscription-info-container">
          {subscription ? (
            <div className="subscription-info">
              <div className={`subscription-badge ${subscription.subscription_type?.toLowerCase()}`}>
                {subscription.subscription_type === 'royal' && <FaCrown className="badge-icon" />}
                {subscription.subscription_type === 'vip' && <FaStar className="badge-icon" />}
                <span>{subscription.subscription_type}</span>
              </div>
              <div className="days-left">
                {t['daysLeft'] || 'Days left'}: <span>{subscription.days_left}</span>
              </div>
            </div>
          ) : (
            <div className="no-subscription-info">
              <FaExclamationCircle className="warning-icon" />
              <span>{t['subscriptionBenefits'] || 'Activate a subscription to access all features'}</span>
            </div>
          )}
        </div>
      </div>

      {/* Active Test Notification */}
      {activeLobby && (
        <div className={`active-test-notification ${isDarkTheme ? 'dark-theme' : ''}`}>
          <div className="notification-icon">
            <FaExclamationCircle />
          </div>
          <div className="notification-content">
            <h3>{t['test.activeTestAvailable'] || 'You have an active test'}</h3>
            <p>
              {t['test.activeTestMessage'] || 'You have an in-progress test. Continue where you left off or start a new test after completing this one.'}
            </p>
            <div className="time-remaining">
              <FaClock /> {t['test.timeRemaining'] || 'Time remaining'}: <span>{formatTime(remainingTime)}</span>
            </div>
          </div>
          <button 
            className={`continue-test-button ${isDarkTheme ? 'dark-theme' : ''}`} 
            onClick={handleContinueTest} 
          >
            <FaPlay />
            <span>{t['test.continueTest'] || 'Continue Test'}</span>
          </button>
        </div>
      )}

      <div className={`progress-divider ${isDarkTheme ? 'dark-theme' : ''}`}>
        <div className="divider-line"></div>
        <div className="divider-text">{t['chooseMode'] || 'Choose testing mode'}</div>
        <div className="divider-line"></div>
      </div>

      {/* Mode Tabs */}
      <div className={`mode-tabs-container ${isDarkTheme ? 'dark-theme' : ''}`}>
        <div className="mode-tabs">
          <button
            className={`mode-tab ${activeTab === 'single' ? 'active' : ''}`}
            onClick={() => setActiveTab('single')}
          >
            <span>{t['test.single_mode'] || 'Одиночный'}</span>
          </button>
          <button
            className={`mode-tab ${activeTab === 'multiplayer' ? 'active' : ''}`}
            onClick={() => setActiveTab('multiplayer')}
          >
            <span>{t['test.multiplayer_mode'] || 'Мультиплеер'}</span>
          </button>
          <div 
            className="tab-indicator" 
            style={{ transform: `translateX(${activeTab === 'single' ? '0' : '100%'})` }}
          />
        </div>
      </div>

      {isLoading ? (
        <div className={`loading-spinner ${isDarkTheme ? 'dark-theme' : ''}`}>
          <div className="spinner"></div>
          <p className="loading-text">{t['loading'] || 'Loading...'}</p>
        </div>
      ) : errorMessage ? (
        <div className={`error-message ${isDarkTheme ? 'dark-theme' : ''}`}>
          <FaExclamationCircle className="error-icon" />
          <span>{errorMessage}</span>
        </div>
      ) : (
        <>
          {activeTab === 'single' ? (
            <>
              <div className={`section-description ${isDarkTheme ? 'dark-theme' : ''}`}>
                <p>{t['test.single_description'] || 'Practice with official exam questions for each license category'}</p>
              </div>
              <div className={`categories-grid ${isDarkTheme ? 'dark-theme' : ''}`}>
                {testCategories.map((category, index) => (
                  <div 
                    key={category.id}
                    className={`category-card ${!isCategoryAvailable(category) ? 'disabled' : ''} ${category.popular ? 'popular' : ''} ${isDarkTheme ? 'dark-theme' : ''}`}
                    onClick={() => isCategoryAvailable(category) && handleStartTest(category)}
                    style={{animationDelay: `${index * 0.1}s`}}
                  >
                    {category.popular && (
                      <div className="popular-badge">
                        <FaTrophy className="popular-icon" />
                        <span>{t['popular'] || 'Popular'}</span>
                      </div>
                    )}
                    <div className="category-icon">
                      {category.icon}
                    </div>
                    <h3 className="category-title">{category.title}</h3>
                    <p className="category-description">{category.description}</p>
                    
                    <div className="category-meta">
                      <div className={`level-badge ${getLevelColor(category.level)}`}>
                        <span>{category.level}</span>
                      </div>
                      <div className="questions-count">
                        {category.questions} {t['questions'] || 'questions'}
                      </div>
                    </div>
                    
                    {isCategoryAvailable(category) ? (
                      <div className={`start-test-button ${isDarkTheme ? 'dark-theme' : ''}`}>
                        <span>{t['startTest'] || 'Start test'}</span>
                        <FaArrowRight className="arrow-icon" />
                      </div>
                    ) : (
                      <div className={`upgrade-overlay ${isDarkTheme ? 'dark-theme' : ''}`}>
                        <FaLock className="lock-icon" />
                        <p>{t['test.upgrade_required'] || 'Upgrade required to access'}</p>
                        <button className={`upgrade-button ${isDarkTheme ? 'dark-theme' : ''}`}>
                          <span>{t['upgrade'] || 'Upgrade'}</span>
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className={`multiplayer-container ${isDarkTheme ? 'dark-theme' : ''}`}>
              <div className={`info-message ${isDarkTheme ? 'dark-theme' : ''}`}>
                <FaInfoCircle className="info-icon" />
                <div>
                  <p className="info-title">{t['multiplayerTitle'] || 'Compete in real-time!'}</p>
                  <p className="info-description">{t['lobbyCreation'] || 'Challenge your friends or other users in real-time tests'}</p>
                </div>
              </div>
              
              <div className="multiplayer-options">
                <div className={`multiplayer-option join-option ${isDarkTheme ? 'dark-theme' : ''}`}>
                  <h3>{t['test.join_lobby'] || 'Присоединиться к лобби'}</h3>
                  <p className="option-description">{t['test.join_description'] || 'Enter a lobby code to join an existing test session'}</p>
                  
                  <div className="lobby-join">
                    <div className="input-with-label">
                      <label htmlFor="lobbyCode">{t['test.lobby_code'] || 'Lobby Code'}</label>
                      <input
                        id="lobbyCode"
                        type="text"
                        value={lobbyCode}
                        onChange={(e) => setLobbyCode(e.target.value)}
                        placeholder={t['test.enter_lobby_code'] || 'Введите код лобби'}
                        className={`lobby-input ${isDarkTheme ? 'dark-theme' : ''}`}
                      />
                    </div>
                    <button 
                      className={`primary-button join-button ${isDarkTheme ? 'dark-theme' : ''}`}
                      onClick={handleJoinLobby}
                      disabled={!lobbyCode.trim()}
                    >
                      <span>{t['test.join'] || 'Присоединиться'}</span>
                      <FaArrowRight className="button-icon" />
                    </button>
                  </div>
                </div>
                
                <div className={`multiplayer-option create-option ${isDarkTheme ? 'dark-theme' : ''}`}>
                  <div className="option-header">
                    <h3>{t['test.create_lobby'] || 'Создать лобби'}</h3>
                    {(!subscription || 
                      !['royal', 'school'].includes(subscription.subscription_type?.toLowerCase())) && (
                      <div className="premium-badge">
                        <FaCrown className="premium-icon" />
                        <span>Royal</span>
                      </div>
                    )}
                  </div>
                  
                  <p className="option-description">{t['test.create_description'] || 'Create your own test lobby and invite friends'}</p>
                  
                  <div className="create-lobby-section">
                    <div className="feature-list">
                      <div className="feature-item">
                        <FaRocket className="feature-icon" />
                        <span>{t['test.feature_custom'] || 'Custom test settings'}</span>
                      </div>
                      <div className="feature-item">
                        <FaTrophy className="feature-icon" />
                        <span>{t['test.feature_leaderboard'] || 'Real-time leaderboard'}</span>
                      </div>
                    </div>
                    
                    <button 
                      className={`primary-button create-button ${isDarkTheme ? 'dark-theme' : ''} ${
                        !subscription || 
                        !['royal', 'school'].includes(subscription.subscription_type?.toLowerCase()) 
                          ? 'disabled' 
                          : ''
                      }`}
                      onClick={handleCreateLobby}
                      disabled={
                        !subscription || 
                        !['royal', 'school'].includes(subscription.subscription_type?.toLowerCase())
                      }
                    >
                      <MdPersonAdd size={20} className="icon-margin" />
                      <span>{t['test.create'] || 'Создать'}</span>
                    </button>
                  </div>
                  
                  {(!subscription || 
                    !['royal', 'school'].includes(subscription.subscription_type?.toLowerCase())) && (
                    <div className={`permission-note ${isDarkTheme ? 'dark-theme' : ''}`}>
                      <FaInfoCircle className="note-icon" />
                      <p>{t['test.royal_school_only'] || 'Доступно только для подписки Royal или School'}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {testModalOpen && (
        <TestModal
          isOpen={testModalOpen}
          onClose={handleCloseModal}
          category={selectedCategory}
          subscription={subscription}
          translations={t}
          isDarkTheme={isDarkTheme}
        />
      )}
    </div>
  );
};

export default TestDashboardPage; 