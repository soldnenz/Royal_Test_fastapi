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
  FaArrowLeft
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

  // Check authentication and load lobby data
  useEffect(() => {
    const checkAuthAndLoadLobby = async () => {
      try {
        console.log('Starting checkAuthAndLoadLobby for lobby:', lobbyId);
        setLoading(true);
        setError('');
        setSubscriptionError('');
        
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
        
        // Try to get user info and subscription
        try {
          console.log('Making API calls to get user info and subscription...');
          // Get user info and subscription
          const [userResponse, subscriptionResponse] = await Promise.all([
            api.get('/users/me'),
            api.get('/users/my/subscription')
          ]);
          console.log('User response:', userResponse.data);
          console.log('Subscription response:', subscriptionResponse.data);
          
          if (userResponse.data.status === 'ok') {
            setIsAuthenticated(true);
            setUserInfo(userResponse.data.data);
            
            // Для лобби созданного School подпиской - любой зарегистрированный пользователь может войти
            if (lobbyData.host_subscription_type?.toLowerCase() === 'school') {
              console.log('School lobby detected, auto-joining registered user');
              await autoJoinLobby();
              return;
            }
            
            // Для остальных лобби проверяем подписку
            if (subscriptionResponse.data.status === 'ok') {
              const subData = subscriptionResponse.data.data;
              setUserSubscription(subData);
              
              // Check subscription access to lobby categories
              const subscription = subscriptionResponse.data.data;
              const lobbyCategories = lobbyData.categories || [];
              
              // Проверяем наличие активной подписки
              if (!subscription.has_subscription) {
                setError('У вас нет активной подписки для доступа к этому лобби.');
                return;
              }
              
              if (lobbyCategories.length > 0) {
                let allowedCategories = [];
                
                switch (subscription.subscription_type?.toLowerCase()) {
                  case 'economy':
                    allowedCategories = ['A1', 'A', 'B1', 'B', 'BE'];
                    break;
                  case 'vip':
                  case 'royal':
                  case 'school':
                    allowedCategories = null; // Полный доступ
                    break;
                  default:
                    // Неизвестный тип подписки - нет доступа
                    setError('Ваш тип подписки не поддерживается для доступа к этому лобби.');
                    return;
                }
                
                // Проверяем доступ к категориям
                if (allowedCategories && !lobbyCategories.some(cat => allowedCategories.includes(cat))) {
                  const allowedStr = allowedCategories.join(', ');
                  const lobbyStr = lobbyCategories.join(', ');
                  setSubscriptionError(
                    `Ваша подписка "${subscription.subscription_type}" имеет доступ только к категориям: ${allowedStr}, а в лобби есть категории: ${lobbyStr}`
                  );
                  return;
                }
              }
              
              // If everything is OK, auto-join
              await autoJoinLobby();
              return;
            } else {
              // Нет подписки - для обычных лобби это ошибка
              setError('У вас нет активной подписки для доступа к этому лобби.');
              return;
            }
          }
        } catch (error) {
          console.error('Error getting user info:', error);
          console.log('User not authenticated or token invalid');
          setIsAuthenticated(false);
          
          // Обрабатываем незарегистрированных пользователей прямо здесь
          console.log('User not authenticated, checking lobby host subscription type:', lobbyData.host_subscription_type);
          // Check if lobby allows guest access (School subscription)
          if (lobbyData.host_subscription_type?.toLowerCase() === 'school') {
            console.log('School lobby detected, showing name input');
            setShowNameInput(true);
          } else {
            console.log('Non-school lobby, showing registration error');
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

  // Loading state
  if (loading) {
    return (
      <div className={`join-lobby-page ${isDark ? 'dark-theme' : ''}`}>
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Загрузка...</p>
        </div>
      </div>
    );
  }

  // Error state for subscription issues
  if (subscriptionError) {
    return (
      <div className={`join-lobby-page ${isDark ? 'dark-theme' : ''}`}>
        <div className="error-container">
          <FaExclamationTriangle />
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
          <FaExclamationTriangle />
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

  // Guest name input for School lobbies
  if (showNameInput && !isAuthenticated) {
    return (
      <div className={`join-lobby-page ${isDark ? 'dark-theme' : ''}`}>
        <div className="join-container">
          <div className="join-header">
            <div className="lobby-icon">
              <FaGamepad />
            </div>
            <h1>Присоединиться к лобби</h1>
            <p>Введите ваше имя для присоединения как гость</p>
          </div>

          {/* Lobby Info */}
          {lobby && (
            <div className="lobby-info">
              <div className="info-grid">
                <div className="info-item">
                  <span className="info-label">ID лобби</span>
                  <span className="info-value">{lobbyId}</span>
                </div>
                
                <div className="info-item">
                  <span className="info-label">Категории</span>
                  <span className="info-value">{lobby.categories?.join(', ') || 'N/A'}</span>
                </div>
                
                <div className="info-item">
                  <span className="info-label">Вопросов</span>
                  <span className="info-value">{lobby.questions_count || 40}</span>
                </div>
                
                <div className="info-item">
                  <span className="info-label">Участники</span>
                  <span className="info-value">
                    {lobby.participants_count || 0}/{lobby.max_participants || 8}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Error message */}
          {error && (
            <div className="error-message">
              <FaExclamationTriangle />
              <span>{error}</span>
            </div>
          )}

          {/* Name input */}
          <div className="name-input-section">
            <div className="name-input-header">
              <FaUser />
              <h3>Введите ваше имя</h3>
              <p>Вы можете присоединиться к этому лобби как гость</p>
            </div>
            
            <div className="name-input-container">
              <input
                type="text"
                value={guestName}
                onChange={(e) => setGuestName(e.target.value)}
                placeholder="Ваше имя"
                className="name-input"
                maxLength={50}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && guestName.trim()) {
                    handleJoinAsGuest();
                  }
                }}
              />
            </div>
          </div>

          {/* Join Button */}
          <div className="join-actions">
            <button
              className={`join-btn ${joining ? 'loading' : ''}`}
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
          </div>
        </div>
      </div>
    );
  }

  // This should not be reached if auto-join works correctly
  return (
    <div className={`join-lobby-page ${isDark ? 'dark-theme' : ''}`}>
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Присоединение к лобби...</p>
      </div>
    </div>
  );
};

export default JoinLobbyPage; 