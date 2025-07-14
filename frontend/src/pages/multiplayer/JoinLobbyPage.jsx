import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useLanguage } from '../../contexts/LanguageContext';
import { useTheme } from '../../contexts/ThemeContext';
import { translations } from '../../translations/translations';
import api from '../../utils/axios';
import { 
  FaUsers,
  FaGamepad,
  FaArrowRight,
  FaExclamationTriangle,
  FaUser,
  FaSpinner,
  FaUserPlus,
  FaSignInAlt,
  FaArrowLeft,
  FaCheckCircle,
  FaLock,
  FaUnlock,
  FaCrown,
  FaGraduationCap
} from 'react-icons/fa';
import './JoinLobbyPage.css';

const JoinLobbyPage = () => {
  const { lobbyId } = useParams();
  const { language } = useLanguage();
  const t = translations[language];
  const { isDark } = useTheme();
  const navigate = useNavigate();
  
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState('');
  const [lobby, setLobby] = useState(null);
  const [userInfo, setUserInfo] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [guestName, setGuestName] = useState('');
  const [showNameInput, setShowNameInput] = useState(false);
  const [subscriptionError, setSubscriptionError] = useState('');
  const [userSubscription, setUserSubscription] = useState(null);
  const [authStatus, setAuthStatus] = useState('checking'); // 'checking', 'authenticated', 'guest', 'unauthenticated'

  // Check authentication and load lobby data
  useEffect(() => {
    const checkAuthAndLoadLobby = async () => {
      try {
        console.log('Starting checkAuthAndLoadLobby for lobby:', lobbyId);
        setLoading(true);
        setError('');
        setSubscriptionError('');
        setAuthStatus('checking');
        
        // Load lobby data using public endpoint first
        console.log('Loading lobby data...');
        const lobbyResponse = await api.get(`/multiplayer/lobbies/${lobbyId}/public`);
        if (lobbyResponse.data.status !== 'ok') {
          setError(lobbyResponse.data.message || 'Лобби не найдено');
          return;
        }
        
        const lobbyData = lobbyResponse.data.data;
        console.log('Lobby data loaded:', lobbyData);
        setLobby(lobbyData);
        
        // Определяем тип лобби
        const isSchoolLobby = lobbyData.host_subscription_type?.toLowerCase() === 'school';
        const isRoyalLobby = lobbyData.host_subscription_type?.toLowerCase() === 'royal';
        
        console.log('Lobby type:', { isSchoolLobby, isRoyalLobby });
        
        // Try to get user info
        try {
          console.log('Checking user authentication...');
          const userResponse = await api.get('/users/me');
          console.log('User response:', userResponse.data);
          
          if (userResponse.data.status === 'ok') {
            setIsAuthenticated(true);
            setUserInfo(userResponse.data.data);
            setAuthStatus('authenticated');
            
            console.log('User authenticated:', userResponse.data.data.full_name);
            
            // Для School лобби - зарегистрированные пользователи присоединяются сразу
            if (isSchoolLobby) {
              console.log('School lobby - registered user can join immediately');
              await autoJoinLobby();
              return;
            }
            
            // Для Royal лобби - проверяем подписку
            if (isRoyalLobby) {
              console.log('Royal lobby - checking subscription');
              try {
                const subscriptionResponse = await api.get('/users/my/subscription');
                console.log('Subscription response:', subscriptionResponse.data);
                
                if (subscriptionResponse.data.status === 'ok') {
                  const subData = subscriptionResponse.data.data;
                  setUserSubscription(subData);
                  
                  // Проверяем наличие активной подписки
                  if (!subData.has_subscription) {
                    setError('Для доступа к Royal лобби требуется активная подписка.');
                    return;
                  }
                  
                  // Проверяем доступ к категориям лобби
                  const lobbyCategories = lobbyData.categories || [];
                  if (lobbyCategories.length > 0) {
                    let allowedCategories = [];
                    
                    switch (subData.subscription_type?.toLowerCase()) {
                      case 'economy':
                        allowedCategories = ['A1', 'A', 'B1', 'B', 'BE'];
                        break;
                      case 'vip':
                      case 'royal':
                      case 'school':
                        allowedCategories = null; // Полный доступ
                        break;
                      default:
                        setError('Ваш тип подписки не поддерживается для доступа к этому лобби.');
                        return;
                    }
                    
                    // Проверяем доступ к категориям
                    if (allowedCategories && !lobbyCategories.some(cat => allowedCategories.includes(cat))) {
                      const allowedStr = allowedCategories.join(', ');
                      const lobbyStr = lobbyCategories.join(', ');
                      setSubscriptionError(
                        `Ваша подписка "${subData.subscription_type}" имеет доступ только к категориям: ${allowedStr}, а в лобби есть категории: ${lobbyStr}`
                      );
                      return;
                    }
                  }
                  
                  // Если все проверки пройдены - присоединяемся
                  await autoJoinLobby();
                  return;
                } else {
                  setError('Для доступа к Royal лобби требуется активная подписка.');
                  return;
                }
              } catch (subscriptionError) {
                console.error('Error getting subscription:', subscriptionError);
                setError('Для доступа к Royal лобби требуется активная подписка.');
                return;
              }
            }
            
            // Для других типов лобби - стандартная проверка подписки
            console.log('Standard lobby - checking subscription');
            try {
              const subscriptionResponse = await api.get('/users/my/subscription');
              console.log('Subscription response:', subscriptionResponse.data);
              
              if (subscriptionResponse.data.status === 'ok') {
                const subData = subscriptionResponse.data.data;
                setUserSubscription(subData);
                
                // Проверяем наличие активной подписки
                if (!subData.has_subscription) {
                  setError('У вас нет активной подписки для доступа к этому лобби.');
                  return;
                }
                
                // Проверяем доступ к категориям
                const lobbyCategories = lobbyData.categories || [];
                if (lobbyCategories.length > 0) {
                  let allowedCategories = [];
                  
                  switch (subData.subscription_type?.toLowerCase()) {
                    case 'economy':
                      allowedCategories = ['A1', 'A', 'B1', 'B', 'BE'];
                      break;
                    case 'vip':
                    case 'royal':
                    case 'school':
                      allowedCategories = null; // Полный доступ
                      break;
                    default:
                      setError('Ваш тип подписки не поддерживается для доступа к этому лобби.');
                      return;
                  }
                  
                  // Проверяем доступ к категориям
                  if (allowedCategories && !lobbyCategories.some(cat => allowedCategories.includes(cat))) {
                    const allowedStr = allowedCategories.join(', ');
                    const lobbyStr = lobbyCategories.join(', ');
                    setSubscriptionError(
                      `Ваша подписка "${subData.subscription_type}" имеет доступ только к категориям: ${allowedStr}, а в лобби есть категории: ${lobbyStr}`
                    );
                    return;
                  }
                }
                
                // Если все проверки пройдены - присоединяемся
                await autoJoinLobby();
                return;
              } else {
                setError('У вас нет активной подписки для доступа к этому лобби.');
                return;
              }
            } catch (subscriptionError) {
              console.error('Error getting subscription:', subscriptionError);
              setError('У вас нет активной подписки для доступа к этому лобби.');
              return;
            }
          }
        } catch (error) {
          console.error('Error getting user info:', error);
          console.log('User not authenticated or token invalid');
          setIsAuthenticated(false);
          setAuthStatus('unauthenticated');
          
          // Обрабатываем незарегистрированных пользователей
          console.log('User not authenticated, checking lobby type');
          
          // Только School лобби позволяют гостевой доступ
          if (isSchoolLobby) {
            console.log('School lobby detected, showing guest access');
            setShowNameInput(true);
            setAuthStatus('guest');
          } else {
            console.log('Non-school lobby, showing registration requirement');
            setError('Вы не зарегистрированы. Только лобби с подпиской School позволяют гостевой доступ.');
          }
        }
        
      } catch (error) {
        console.error('Error loading lobby:', error);
        if (error.response?.status === 404) {
          setError('Лобби не найдено');
        } else {
          setError(error.response?.data?.message || 'Ошибка загрузки лобби');
        }
      } finally {
        setLoading(false);
      }
    };

    if (lobbyId) {
      checkAuthAndLoadLobby();
    }
  }, [lobbyId]);

  // Auto-join lobby for authenticated users
  const autoJoinLobby = async () => {
    try {
      setJoining(true);
      const joinResponse = await api.post(`/multiplayer/lobbies/${lobbyId}/join`);
      
      if (joinResponse.data.status === 'ok') {
        const wsToken = joinResponse.data.data.ws_token;
        if (wsToken) {
          localStorage.removeItem('ws_token');
          localStorage.setItem('ws_token', wsToken);
        }
        // Redirect to lobby waiting page immediately
        navigate(`/multiplayer/lobby/${lobbyId}`, { replace: true });
      } else {
        setError(joinResponse.data.message || 'Не удалось присоединиться к лобби');
      }
    } catch (error) {
      console.error('Error auto-joining lobby:', error);
      setError(error.response?.data?.message || 'Не удалось присоединиться к лобби');
    } finally {
      setJoining(false);
    }
  };

  // Join lobby as guest
  const handleJoinAsGuest = async () => {
    try {
      setJoining(true);
      setError('');

      if (!guestName.trim()) {
        setError('Пожалуйста, введите ваше имя');
        return;
      }

      // Register as guest user
      const guestResponse = await api.post('/auth/guest-register', {
        name: guestName.trim(),
        lobby_id: lobbyId
      });

      if (guestResponse.data.status !== 'ok') {
        setError(guestResponse.data.message || 'Не удалось зарегистрироваться как гость');
        return;
      }

      // Store guest token  
      const guestToken = guestResponse.data.data.access_token;
      localStorage.setItem('token', guestToken);
      localStorage.setItem('isGuest', 'true');

      // Set cookie for backend authentication
      document.cookie = `access_token=${guestToken}; path=/; SameSite=Lax`;

      // Update axios defaults to include the new token
      api.defaults.headers.common['Authorization'] = `Bearer ${guestToken}`;

      // Join the lobby
      const joinResponse = await api.post(`/multiplayer/lobbies/${lobbyId}/join`);
      
      if (joinResponse.data.status === 'ok') {
        const wsToken = joinResponse.data.data.ws_token;
        if (wsToken) {
          localStorage.removeItem('ws_token');
          localStorage.setItem('ws_token', wsToken);
        }
        // Redirect to lobby waiting page
        navigate(`/multiplayer/lobby/${lobbyId}`, { replace: true });
      } else {
        setError(joinResponse.data.message || 'Не удалось присоединиться к лобби');
      }
    } catch (error) {
      console.error('Error joining as guest:', error);
      setError(error.response?.data?.message || 'Не удалось присоединиться к лобби');
    } finally {
      setJoining(false);
    }
  };

  // Get subscription icon
  const getSubscriptionIcon = (type) => {
    switch (type?.toLowerCase()) {
      case 'school':
        return <FaGraduationCap className="subscription-icon school" />;
      case 'royal':
        return <FaCrown className="subscription-icon royal" />;
      case 'vip':
        return <FaCrown className="subscription-icon vip" />;
      default:
        return <FaUser className="subscription-icon" />;
    }
  };

  // Get lobby type description
  const getLobbyTypeDescription = () => {
    const lobbyType = lobby?.host_subscription_type?.toLowerCase();
    switch (lobbyType) {
      case 'school':
        return {
          title: 'Школьное лобби',
          description: 'Любой зарегистрированный пользователь может присоединиться. Гости могут войти, указав имя.',
          icon: <FaGraduationCap className="lobby-type-icon school" />
        };
      case 'royal':
        return {
          title: 'Royal лобби',
          description: 'Требуется регистрация и активная подписка, покрывающая категории лобби.',
          icon: <FaCrown className="lobby-type-icon royal" />
        };
      default:
        return {
          title: 'Стандартное лобби',
          description: 'Требуется регистрация и активная подписка.',
          icon: <FaUser className="lobby-type-icon" />
        };
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className={`join-lobby-page ${isDark ? 'dark-theme' : ''}`}>
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Загрузка лобби...</p>
        </div>
      </div>
    );
  }

  // Error state for subscription issues
  if (subscriptionError) {
    return (
      <div className={`join-lobby-page ${isDark ? 'dark-theme' : ''}`}>
        <div className="error-container">
          <FaExclamationTriangle className="error-icon" />
          <h2>Недостаточно прав доступа</h2>
          <p>{subscriptionError}</p>
          <button className="back-btn" onClick={() => navigate('/dashboard')}>
            <FaArrowLeft />
            Обратно на дашборд
          </button>
        </div>
      </div>
    );
  }

  // Error state for unauthenticated users (non-School lobbies)
  if (error && !showNameInput) {
    return (
      <div className={`join-lobby-page ${isDark ? 'dark-theme' : ''}`}>
        <div className="error-container">
          <FaExclamationTriangle className="error-icon" />
          <h2>Требуется регистрация</h2>
          <p>{error}</p>
          <div className="auth-buttons">
            <button className="register-btn" onClick={() => navigate('/register')}>
              <FaUserPlus />
              Зарегистрироваться
            </button>
            <button className="login-btn" onClick={() => navigate('/login')}>
              <FaSignInAlt />
              Войти
            </button>
          </div>
        </div>
      </div>
    );
  }

  const lobbyTypeInfo = getLobbyTypeDescription();

  // Main join lobby interface
  return (
    <div className={`join-lobby-page ${isDark ? 'dark-theme' : ''}`}>
      <div className="join-container">
        {/* Header */}
        <div className="join-header">
          <div className="lobby-icon">
            <FaGamepad />
          </div>
          <h1>Присоединиться к лобби</h1>
          <p>ID: {lobbyId}</p>
        </div>

        {/* Lobby Type Info */}
        <div className="lobby-type-card">
          <div className="lobby-type-header">
            {lobbyTypeInfo.icon}
            <h3>{lobbyTypeInfo.title}</h3>
          </div>
          <p className="lobby-type-description">{lobbyTypeInfo.description}</p>
        </div>

        {/* Lobby Info Card */}
        {lobby && (
          <div className="lobby-info-card">
            <div className="lobby-info-header">
              <h3>Информация о лобби</h3>
              <div className="host-info">
                <span>Создатель: {lobby.host_name || 'Неизвестный'}</span>
                {getSubscriptionIcon(lobby.host_subscription_type)}
              </div>
            </div>
            
            <div className="lobby-stats">
              <div className="stat-item">
                <span className="stat-label">Категории</span>
                <span className="stat-value">{lobby.categories?.join(', ') || 'Все'}</span>
              </div>
              
              <div className="stat-item">
                <span className="stat-label">Вопросов</span>
                <span className="stat-value">{lobby.questions_count || 40}</span>
              </div>
              
              <div className="stat-item">
                <span className="stat-label">Участники</span>
                <span className="stat-value">
                  {lobby.participants_count || 0}/{lobby.max_participants || 8}
                </span>
              </div>
              
              <div className="stat-item">
                <span className="stat-label">Статус</span>
                <span className={`stat-value status-${lobby.status}`}>
                  {lobby.status === 'waiting' ? 'Ожидание' : 
                   lobby.status === 'in_progress' ? 'В процессе' : 'Завершено'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Authentication Status */}
        <div className="auth-status-card">
          {authStatus === 'checking' && (
            <div className="status-checking">
              <FaSpinner className="spinning" />
              <span>Проверка доступа...</span>
            </div>
          )}
          
          {authStatus === 'authenticated' && (
            <div className="status-authenticated">
              <FaCheckCircle className="status-icon success" />
              <div className="status-content">
                <h4>Вы авторизованы</h4>
                <p>{userInfo?.full_name || 'Пользователь'}</p>
                {userSubscription && (
                  <div className="subscription-info">
                    <span>Подписка: {userSubscription.subscription_type}</span>
                  </div>
                )}
              </div>
            </div>
          )}
          
          {authStatus === 'guest' && (
            <div className="status-guest">
              <FaUnlock className="status-icon guest" />
              <div className="status-content">
                <h4>Гостевой доступ</h4>
                <p>Это лобби позволяет присоединиться как гость</p>
              </div>
            </div>
          )}
          
          {authStatus === 'unauthenticated' && (
            <div className="status-unauthenticated">
              <FaLock className="status-icon error" />
              <div className="status-content">
                <h4>Требуется регистрация</h4>
                <p>Для присоединения к этому лобби необходимо зарегистрироваться</p>
              </div>
            </div>
          )}
        </div>

        {/* Error message */}
        {error && (
          <div className="error-message">
            <FaExclamationTriangle />
            <span>{error}</span>
          </div>
        )}

        {/* Guest name input for School lobbies */}
        {showNameInput && authStatus === 'guest' && (
          <div className="guest-input-section">
            <div className="guest-input-header">
              <FaUser />
              <h3>Введите ваше имя</h3>
              <p>Вы можете присоединиться к этому лобби как гость</p>
            </div>
            
            <div className="guest-input-container">
              <input
                type="text"
                value={guestName}
                onChange={(e) => setGuestName(e.target.value)}
                placeholder="Ваше имя"
                className="guest-name-input"
                maxLength={50}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && guestName.trim()) {
                    handleJoinAsGuest();
                  }
                }}
              />
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="join-actions">
          {authStatus === 'authenticated' && !joining && (
            <button
              className="join-btn primary"
              onClick={autoJoinLobby}
            >
              <FaUsers />
              Присоединиться к лобби
              <FaArrowRight />
            </button>
          )}
          
          {authStatus === 'guest' && (
            <button
              className={`join-btn ${joining ? 'loading' : 'secondary'}`}
              onClick={handleJoinAsGuest}
              disabled={joining || !guestName.trim()}
            >
              {joining ? (
                <>
                  <FaSpinner className="spinning" />
                  Присоединение...
                </>
              ) : (
                <>
                  <FaUsers />
                  Присоединиться как гость
                  <FaArrowRight />
                </>
              )}
            </button>
          )}
          
          {authStatus === 'unauthenticated' && (
            <div className="auth-buttons">
              <button className="register-btn" onClick={() => navigate('/register')}>
                <FaUserPlus />
                Зарегистрироваться
              </button>
              <button className="login-btn" onClick={() => navigate('/login')}>
                <FaSignInAlt />
                Войти
              </button>
            </div>
          )}
          
          {joining && (
            <div className="joining-status">
              <FaSpinner className="spinning" />
              <span>Присоединение к лобби...</span>
            </div>
          )}
        </div>

        {/* Back Button */}
        <div className="back-section">
          <button className="back-btn secondary" onClick={() => navigate('/dashboard')}>
            <FaArrowLeft />
            Обратно на дашборд
          </button>
        </div>
      </div>
    </div>
  );
};

export default JoinLobbyPage; 