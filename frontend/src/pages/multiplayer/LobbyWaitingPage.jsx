import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useLanguage } from '../../contexts/LanguageContext';
import { useTheme } from '../../contexts/ThemeContext';
import { translations } from '../../translations/translations';
import api from '../../utils/axios';
import QRCode from 'qrcode';
import Header from '../../components/Header';
import Sidebar from '../../components/dashboard/DashboardSidebar';
import useLobbyWebSocket from '../../hooks/useLobbyWebSocket';
import { 
  FaTimes, 
  FaPlay, 
  FaCrown, 
  FaGraduationCap,
  FaArrowLeft,
  FaUsers,
  FaQuestionCircle,
  FaCog,
  FaClock,
  FaLink,
  FaCopy,
  FaUserTimes,
  FaExclamationTriangle,
  FaWifi,
  FaTruck, 
  FaTruckMoving, 
  FaBusAlt,
  FaSignOutAlt,
  FaCheck
} from 'react-icons/fa';
import { 
  MdDirectionsBike, 
  MdDirectionsCar, 
  MdLocalShipping, 
  MdTimer 
} from 'react-icons/md';
import './LobbyWaitingPage.css';

const LobbyWaitingPage = () => {
  const { lobbyId } = useParams();
  const { language } = useLanguage();
  const t = translations[language];
  const { isDark } = useTheme();
  const navigate = useNavigate();
  
  const [lobby, setLobby] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [qrCodeUrl, setQrCodeUrl] = useState('');
  const [copySuccess, setCopySuccess] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const [userSubscription, setUserSubscription] = useState(null);
  const [subscriptionError, setSubscriptionError] = useState('');
  const [canJoinLobby, setCanJoinLobby] = useState(false);
  const [hasTriedToJoin, setHasTriedToJoin] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [qrModalOpen, setQrModalOpen] = useState(false);
  const [currentUserId, setCurrentUserId] = useState(null);
  
  const timeLeftRef = useRef(0);

  // WebSocket connection for lobby
  const {
    isConnected: wsConnected,
    reconnectAttempts,
    participants,
    connect: connectWebSocket,
    disconnect: disconnectWebSocket,
    reconnect: reconnectWebSocket,
    updateParticipantsStatus,
    setParticipants
  } = useLobbyWebSocket(lobbyId);

  // Get current user ID from API
  const getCurrentUserId = useCallback(async () => {
    try {
      const response = await api.get('/users/me');
      if (response.data.status === 'ok' && response.data.data) {
        return response.data.data.id || response.data.data._id;
      }
    } catch (error) {
      console.error('Error getting current user ID:', error);
    }
    return null;
  }, []);

  // Fetch lobby data
  const fetchLobbyData = async () => {
    try {
      const response = await api.get(`/lobbies/lobbies/${lobbyId}`);
      
      if (response.data.status === 'ok') {
        const lobbyData = response.data.data;
        setLobby(lobbyData);
        
        // Check subscription access - inline to avoid circular dependencies
        const hasAccess = await (async () => {
          try {
            const userId = await getCurrentUserId();
            setCurrentUserId(userId);
            const isHost = userId && lobbyData.host_id === userId;
            
            if (isHost) {
              setCanJoinLobby(true);
              return true;
            }
            
            // Для лобби созданного School подпиской - любой может войти
            if (lobbyData.host_subscription_type?.toLowerCase() === 'school') {
              setCanJoinLobby(true);
              return true;
            }
            
            const subscriptionResponse = await api.get('/users/my/subscription');
            
            if (subscriptionResponse.data.status === 'ok') {
              const subData = subscriptionResponse.data.data;
              
              if (subData.has_subscription) {
                const subscription = {
                  subscription_type: subData.subscription_type,
                  expires_at: subData.expires_at,
                  days_left: subData.days_left,
                  duration_days: subData.duration_days
                };
                setUserSubscription(subscription);
                
                const lobbyCategories = lobbyData.categories || [];
                const userSubscriptionType = subscription.subscription_type.toLowerCase();
                
                let allowedCategories = [];
                switch (userSubscriptionType) {
                  case 'economy':
                    allowedCategories = ['A1', 'A', 'B1', 'B', 'BE'];
                    break;
                  case 'vip':
                  case 'royal':
                  case 'school':
                    allowedCategories = null;
                    break;
                  default:
                    allowedCategories = ['B'];
                }
                
                if (allowedCategories && lobbyCategories.length > 0) {
                  const hasAccessToCategories = lobbyCategories.some(cat => allowedCategories.includes(cat));
                  if (!hasAccessToCategories) {
                    setSubscriptionError(
                      `Ваша подписка "${subscription.subscription_type}" рассчитана на категории: ${allowedCategories.join(', ')}, ` +
                      `а лобби настроено на категории: ${lobbyCategories.join(', ')}`
                    );
                    setCanJoinLobby(false);
                    return false;
                  }
                }
                
                setCanJoinLobby(true);
                return true;
                
              } else {
                // Нет подписки - для обычных лобби это ошибка
                setSubscriptionError('Вы не зарегистрированы или у вас нет подписки');
                setCanJoinLobby(false);
                return false;
              }
            } else {
              setSubscriptionError('Не удалось получить информацию о подписке');
              setCanJoinLobby(false);
              return false;
            }
          } catch (error) {
            console.error('Error checking subscription:', error);
            setSubscriptionError('Ошибка при проверке подписки');
            setCanJoinLobby(false);
            return false;
          }
        })();
        
        // Auto-join if access is granted
        if (hasAccess && !hasTriedToJoin) {
          const userId = await getCurrentUserId();
          if (userId && !lobbyData.participants?.includes(userId)) {
            setHasTriedToJoin(true);
            try {
              const response = await api.post(`/lobbies/lobbies/${lobbyId}/join`);
              if (response.data.status === 'ok') {
                console.log('Successfully joined lobby');
              } else {
                setError(response.data.message || 'Failed to join lobby');
              }
            } catch (error) {
              console.error('Error joining lobby:', error);
              setError(error.response?.data?.message || 'Failed to join lobby');
            }
          }
        }
        
        // Calculate time left - используем время с сервера если доступно
        let timeLeftSeconds = 0;
        
        if (lobbyData.remaining_seconds !== undefined) {
          // Если сервер предоставляет remaining_seconds, используем его
          timeLeftSeconds = Math.max(0, lobbyData.remaining_seconds);
        } else {
          // Fallback: вычисляем на клиенте (4 часа от создания)
          try {
            // Парсим время создания - добавляем 'Z' если его нет для UTC
            let createdAtString = lobbyData.created_at;
            if (!createdAtString.endsWith('Z') && !createdAtString.includes('+')) {
              createdAtString += 'Z';
            }
            
            const createdAt = new Date(createdAtString);
            const expiresAt = new Date(createdAt.getTime() + 4 * 60 * 60 * 1000); // 4 hours
            const now = new Date();
            timeLeftSeconds = Math.max(0, Math.floor((expiresAt - now) / 1000));
            
            console.log('Lobby time calculation (fallback):', {
              created_at: lobbyData.created_at,
              createdAtString,
              createdAt: createdAt.toISOString(),
              expiresAt: expiresAt.toISOString(),
              now: now.toISOString(),
              timeLeftSeconds
            });
          } catch (error) {
            console.error('Error calculating lobby time:', error);
            // Если не можем вычислить время, устанавливаем 4 часа
            timeLeftSeconds = 4 * 60 * 60; // 4 hours
          }
        }
        
        console.log('Final timeLeftSeconds:', timeLeftSeconds);
        setTimeLeft(timeLeftSeconds);
        timeLeftRef.current = timeLeftSeconds;
        
        // Get participant details
        const participantsIds = lobbyData.participants || [];
        if (Array.isArray(participantsIds) && participantsIds.length > 0) {
          const participantPromises = participantsIds.map(async (userId) => {
            try {
              const userResponse = await api.get(`/users/${userId}`);
              return {
                id: userId,
                name: userResponse.data.data?.full_name || 'Unknown User',
                online: true // This would be updated via WebSocket
              };
            } catch (error) {
              console.error(`Failed to fetch user ${userId}:`, error);
              return {
                id: userId,
                name: 'Unknown User',
                online: true // Считаем участников онлайн по умолчанию
              };
            }
          });
          
          const participantDetails = await Promise.all(participantPromises);
          
          // Убеждаемся, что текущий пользователь в списке
          const userId = await getCurrentUserId();
          if (userId && !participantDetails.some(p => p.id === userId)) {
                          try {
                const currentUserResponse = await api.get(`/users/${userId}`);
                participantDetails.push({
                  id: userId,
                  name: currentUserResponse.data.data?.full_name || 'You',
                  online: true
                });
              } catch (error) {
                console.error('Failed to fetch current user:', error);
                participantDetails.push({
                  id: userId,
                  name: 'You',
                  online: true
                });
              }
          }
          
          setParticipants(() => participantDetails);
        } else {
          setParticipants(() => []);
        }
        
      } else {
        setError(response.data.message || t['failedToLoadLobby'] || 'Failed to load lobby');
      }
    } catch (error) {
      console.error('Error fetching lobby data:', error);
      setError(error.response?.data?.message || t['failedToLoadLobby'] || 'Failed to load lobby');
    }
  };

  // Handle WebSocket events and lobby status changes
  useEffect(() => {
    // Poll lobby status to detect when test starts
    const statusCheckInterval = setInterval(async () => {
      try {
        const response = await api.get(`/lobbies/lobbies/${lobbyId}`);
        if (response.data.status === 'ok') {
          const lobbyData = response.data.data;
          
          // If lobby status changed to active/in_progress, navigate to test
          if (lobbyData.status === 'active' || lobbyData.status === 'in_progress') {
            clearInterval(statusCheckInterval);
            navigate(`/multiplayer/test/${lobbyId}`);
          }
          
          // If lobby was completed or closed, handle appropriately
          else if (lobbyData.status === 'completed' || lobbyData.status === 'inactive') {
            clearInterval(statusCheckInterval);
            setError('Лобби было закрыто');
            setTimeout(() => {
              navigate('/dashboard', { replace: true });
            }, 3000);
          }
        }
      } catch (error) {
        // Ignore polling errors, continue checking
        console.log('Status check error (ignored):', error);
      }
    }, 2000); // Check every 2 seconds

    // Listen for kick events
    const handleKick = (data) => {
      if (data.kicked_user_id === currentUserId) {
        clearInterval(statusCheckInterval);
        setError('Вы были исключены из лобби');
        setTimeout(() => {
          navigate('/dashboard', { replace: true });
        }, 3000);
      }
    };

    // Listen for lobby close events
    const handleLobbyClose = () => {
      clearInterval(statusCheckInterval);
      setError('Лобби было закрыто хостом');
      setTimeout(() => {
        navigate('/dashboard', { replace: true });
      }, 3000);
    };

    // Cleanup on unmount
    return () => {
      clearInterval(statusCheckInterval);
    };
    
  }, [lobbyId, navigate, currentUserId]);

  // Category icons mapping
  const getCategoryIcon = (categories) => {
    if (categories.includes('A1') || categories.includes('A') || categories.includes('B1')) {
      return <MdDirectionsBike size={20} />;
    }
    if (categories.includes('B') || categories.includes('BE')) {
      return <MdDirectionsCar size={20} />;
    }
    if (categories.includes('C') || categories.includes('C1')) {
      return <FaTruck size={20} />;
    }
    if (categories.includes('BC1')) {
      return <FaTruckMoving size={20} />;
    }
    if (categories.includes('D1') || categories.includes('D') || categories.includes('Tb')) {
      return <FaBusAlt size={20} />;
    }
    if (categories.includes('CE') || categories.includes('DE')) {
      return <MdLocalShipping size={20} />;
    }
    if (categories.includes('Tm')) {
      return <MdTimer size={20} />;
    }
    return <MdDirectionsCar size={20} />;
  };

  // Format time from seconds to HH:MM:SS
  const formatTime = (totalSeconds) => {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  // Generate QR code
  const generateQRCode = async (url) => {
    try {
      const qrDataUrl = await QRCode.toDataURL(url, {
        width: 200,
        margin: 2,
        color: {
          dark: isDark ? '#f1f5f9' : '#1e293b',
          light: isDark ? '#1e293b' : '#ffffff'
        }
      });
      setQrCodeUrl(qrDataUrl);
    } catch (error) {
      console.error('Error generating QR code:', error);
    }
  };

  // Copy lobby link
  const copyLobbyLink = async () => {
    const lobbyUrl = `${window.location.origin}/multiplayer/join/${lobbyId}`;
    try {
      await navigator.clipboard.writeText(lobbyUrl);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch (error) {
      console.error('Failed to copy link:', error);
    }
  };

  // Countdown timer
  useEffect(() => {
    // Не запускаем таймер, пока лобби не загружено
    if (!lobby) return;
    
    const timer = setInterval(() => {
      if (timeLeftRef.current > 0) {
        timeLeftRef.current -= 1;
        setTimeLeft(timeLeftRef.current);
      } else {
        clearInterval(timer);
        setError(t['lobbyExpired'] || 'Lobby has expired');
        setTimeout(() => {
          navigate('/dashboard');
        }, 3000);
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [lobby, navigate, t]); // Добавляем lobby в зависимости

  // Initialize
  useEffect(() => {
    const initialize = async () => {
      setLoading(true);
      await fetchLobbyData();
      setLoading(false);
    };

    initialize();
  }, [lobbyId]);

  // Generate QR code when lobby is loaded
  useEffect(() => {
    if (lobby) {
      const lobbyUrl = `${window.location.origin}/multiplayer/join/${lobbyId}`;
      generateQRCode(lobbyUrl);
    }
  }, [lobby, lobbyId, isDark]);

  // Start test
  const handleStartTest = async () => {
    try {
      setLoading(true);
      const response = await api.post(`/lobbies/lobbies/${lobbyId}/start`);
      
      if (response.data.status === 'ok') {
        // Wait a moment for the lobby status to update, then navigate
        setTimeout(() => {
          navigate(`/multiplayer/test/${lobbyId}`);
        }, 1000);
      } else {
        setError(response.data.message || t['failedToStartTest'] || 'Failed to start test');
      }
    } catch (error) {
      console.error('Error starting test:', error);
      setError(error.response?.data?.message || t['failedToStartTest'] || 'Failed to start test');
    } finally {
      setLoading(false);
    }
  };

  // Close lobby
  const handleCloseLobby = async () => {
    if (!confirm(t['confirmCloseLobby'] || 'Are you sure you want to close this lobby?')) {
      return;
    }
    
    try {
      setLoading(true);
      
      // Close WebSocket connection first
      disconnectWebSocket(1000, 'Lobby closed by host');
      
      const response = await api.post(`/lobbies/lobbies/${lobbyId}/close`);
      
      if (response.data.status === 'ok') {
        // Force navigation after a short delay
        setTimeout(() => {
          navigate('/dashboard', { replace: true });
        }, 500);
      } else {
        setError(response.data.message || t['failedToCloseLobby'] || 'Failed to close lobby');
      }
    } catch (error) {
      console.error('Error closing lobby:', error);
      setError(error.response?.data?.message || t['failedToCloseLobby'] || 'Failed to close lobby');
      // Navigate anyway after error
      setTimeout(() => {
        navigate('/dashboard', { replace: true });
      }, 2000);
    } finally {
      setLoading(false);
    }
  };

  // Kick participant (host only)
  const handleKickParticipant = async (userId) => {
    if (!confirm(t['confirmKickUser'] || 'Are you sure you want to kick this user?')) {
      return;
    }
    
    try {
      const response = await api.post(`/lobbies/lobbies/${lobbyId}/kick`, { target_user_id: userId });
      
      if (response.data.status === 'ok') {
        // WebSocket will handle the update, no need to manually refresh
        console.log('User kicked successfully');
      } else {
        setError(response.data.message || t['failedToKickUser'] || 'Failed to kick user');
      }
    } catch (error) {
      console.error('Error kicking user:', error);
      setError(error.response?.data?.message || t['failedToKickUser'] || 'Failed to kick user');
    }
  };

  // Leave lobby (non-host only)
  const handleLeaveLobby = async () => {
    if (!confirm('Вы действительно хотите выйти из лобби?')) {
      return;
    }
    
    try {
      const response = await api.post(`/lobbies/lobbies/${lobbyId}/leave`);
      
      if (response.data.status === 'ok') {
        // Navigate back to dashboard
        navigate('/dashboard', { replace: true });
      } else {
        setError(response.data.message || 'Не удалось выйти из лобби');
      }
    } catch (error) {
      console.error('Error leaving lobby:', error);
      setError(error.response?.data?.message || 'Не удалось выйти из лобби');
    }
  };

  // Периодическое обновление статуса участников
  useEffect(() => {
    if (!lobby || lobby.status !== 'waiting') return;
    
    // Обновляем статус каждые 15 секунд
    const statusInterval = setInterval(() => {
      updateParticipantsStatus();
    }, 15000);
    
    // Первое обновление сразу
    updateParticipantsStatus();
    
    return () => clearInterval(statusInterval);
  }, [lobby, lobbyId, updateParticipantsStatus]);

  if (loading && !lobby) {
    return (
      <div className={`lobby-waiting-page ${isDark ? 'dark-theme' : ''}`}>
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>{t['loading'] || 'Loading...'}</p>
        </div>
      </div>
    );
  }

  if (error && !lobby) {
    return (
      <div className={`lobby-waiting-page ${isDark ? 'dark-theme' : ''}`}>
        <div className="error-container">
          <FaExclamationTriangle />
          <p>{error}</p>
          <button className="back-btn" onClick={() => navigate('/dashboard')}>
            <FaArrowLeft />
            {t['backToDashboard'] || 'Back to Dashboard'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`lobby-waiting-page ${isDark ? 'dark-theme' : ''}`}>
      <Header />
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      
      <div className="main-content">
        <div className="lobby-container">
          {/* Lobby Header */}
          <div className="lobby-header">
            <div className="header-left">
              <button className="sidebar-toggle-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <button className="back-btn" onClick={() => navigate('/dashboard')}>
                <FaArrowLeft />
              </button>
            </div>
            <div className="header-content">
              <h1>{t['lobby'] || 'Лобби'}</h1>
            </div>
            <div className="connection-status">
              {wsConnected ? (
                <div className="status-indicator online">
                  <FaWifi />
                  <span>{t['connected'] || 'Connected'}</span>
                </div>
              ) : (
                <div className="status-indicator offline">
                  <FaExclamationTriangle />
                  <span>
                    {reconnectAttempts > 0 
                      ? `${t['reconnecting'] || 'Переподключение'} (${reconnectAttempts}/5)`
                      : (t['connecting'] || 'Connecting...')
                    }
                  </span>
                  <button 
                    className="reconnect-btn"
                    onClick={reconnectWebSocket}
                    title="Переподключиться"
                  >
                    <FaWifi />
                  </button>
                </div>
              )}
            </div>
          </div>

        {/* Error message */}
        {error && (
          <div className="error-message">
            <FaExclamationTriangle />
            <span>{error}</span>
          </div>
        )}

        {/* Subscription Error message */}
        {subscriptionError && !canJoinLobby && (
          <div className="subscription-error-message">
            <FaExclamationTriangle />
            <div className="subscription-error-content">
              <h3>Доступ к лобби ограничен</h3>
              <p>{subscriptionError}</p>
              {userSubscription ? (
                <div className="subscription-info">
                  <p><strong>Ваша подписка:</strong> {userSubscription.subscription_type}</p>
                  <p><strong>Действует до:</strong> {new Date(userSubscription.expires_at).toLocaleDateString()}</p>
                </div>
              ) : (
                <div className="no-subscription-info">
                  <p>У вас нет активной подписки</p>
                  <button 
                    className="get-subscription-btn"
                    onClick={() => navigate('/subscription')}
                  >
                    Получить подписку
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="lobby-content">
          {/* Lobby Settings */}
          <div className="lobby-settings">
            <h2>{t['lobbySettings'] || 'Lobby Settings'}</h2>
            
            <div className="settings-grid">
              <div className="setting-item">
                <div className="setting-icon">
                  {getCategoryIcon(lobby?.categories || [])}
                </div>
                <div className="setting-content">
                  <span className="setting-label">{t['categories'] || 'Categories'}</span>
                  <span className="setting-value">{lobby?.categories?.join(', ') || 'N/A'}</span>
                </div>
              </div>

              <div className="setting-item">
                <div className="setting-icon">
                  <FaQuestionCircle />
                </div>
                <div className="setting-content">
                  <span className="setting-label">{t['questions'] || 'Questions'}</span>
                  <span className="setting-value">{lobby?.questions_count || 'N/A'}</span>
                </div>
              </div>

              <div className="setting-item">
                <div className="setting-icon">
                  <FaUsers />
                </div>
                <div className="setting-content">
                  <span className="setting-label">{t['maxParticipants'] || 'Max Participants'}</span>
                  <span className="setting-value">{lobby?.max_participants || 8}</span>
                </div>
              </div>

              <div className="setting-item">
                <div className="setting-icon">
                  <FaCog />
                </div>
                <div className="setting-content">
                  <span className="setting-label">{t['examMode'] || 'Exam Mode'}</span>
                  <span className="setting-value">
                    {lobby?.exam_mode ? (t['enabled'] || 'Enabled') : (t['disabled'] || 'Disabled')}
                  </span>
                </div>
              </div>
            </div>

            {/* Time remaining */}
            <div className="time-remaining">
              <FaClock />
              <span>{t['lobbyExpiresIn'] || 'Lobby expires in'}: </span>
              <span className="time-value">{formatTime(timeLeft)}</span>
            </div>
          </div>

          {/* Lobby ID */}
          <div className="lobby-id-section">
            <div className="lobby-id-container">
              <span className="lobby-id-label">ID:</span>
              <span className="lobby-id-value">{lobbyId}</span>
            </div>
          </div>

          {/* QR Code and Join Link */}
          <div className="join-section">
            <h2>{t['joinLobby'] || 'Join Lobby'}</h2>
            
            <div className="qr-container">
              {qrCodeUrl && (
                <img 
                  src={qrCodeUrl} 
                  alt="QR Code" 
                  className="qr-code" 
                  onClick={() => setQrModalOpen(true)}
                />
              )}
            </div>
            
            <div className="join-link">
              <div className="link-container">
                <FaLink />
                <span className="link-text">
                  {`${window.location.origin}/multiplayer/join/${lobbyId}`}
                </span>
                <button 
                  className={`copy-btn ${copySuccess ? 'success' : ''}`}
                  onClick={copyLobbyLink}
                >
                  {copySuccess ? <FaCheck /> : <FaCopy />}
                </button>
              </div>
            </div>
          </div>

          {/* Participants */}
          <div className="participants-section">
            <div className="participants-header">
              <h2>{t['participants'] || 'Participants'}</h2>
              <span className="participants-count">
                {participants.length}/{lobby?.max_participants || 8}
              </span>
            </div>
            
            <div className="participants-list">
              {Array.isArray(participants) && participants.map((participant, index) => (
                <div 
                  key={participant.id} 
                  className={`participant-item ${!participant.online ? 'offline' : ''}`}
                >
                  <div className="participant-info">
                    <div className="participant-avatar">
                      {participant.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="participant-details">
                      <span className="participant-name">{participant.name}</span>
                      <span className="participant-status">
                        {participant.id === lobby?.host_id && (
                          <>
                            {lobby?.host_subscription_type === 'royal' ? <FaCrown /> : <FaGraduationCap />}
                            {t['host'] || 'Host'}
                          </>
                        )}
                        {participant.id !== lobby?.host_id && (
                          <>
                            {participant.online ? (
                              <>
                                <div className="status-dot online"></div>
                                {t['online'] || 'Online'}
                              </>
                            ) : (
                              <>
                                <div className="status-dot offline"></div>
                                {t['offline'] || 'Offline'}
                              </>
                            )}
                          </>
                        )}
                      </span>
                    </div>
                  </div>
                  
                  {lobby?.is_host && participant.id !== lobby?.host_id && (
                    <button 
                      className="kick-btn"
                      onClick={() => handleKickParticipant(participant.id)}
                      title={t['kickUser'] || 'Kick user'}
                    >
                      <FaUserTimes />
                    </button>
                  )}
                </div>
              ))}
              
              {/* Empty slots */}
              {Array.from({ length: (lobby?.max_participants || 8) - participants.length }, (_, index) => (
                <div key={`empty-${index}`} className="participant-item empty">
                  <div className="participant-info">
                    <div className="participant-avatar empty">?</div>
                    <div className="participant-details">
                      <span className="participant-name">{t['waitingForPlayer'] || 'Waiting for player...'}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        {lobby?.is_host ? (
          <div className="lobby-actions">
            <button 
              className="action-btn close-btn"
              onClick={handleCloseLobby}
              disabled={loading}
            >
              <FaTimes />
              {t['closeLobby'] || 'Закрыть лобби'}
            </button>
            
            <button 
              className={`action-btn start-btn ${loading ? 'loading' : ''}`}
              onClick={handleStartTest}
              disabled={loading || participants.length < 2}
            >
              {loading ? (
                <div className="spinner"></div>
              ) : (
                <>
                  <FaPlay />
                  {t['startTest'] || 'Начать тест'}
                </>
              )}
            </button>
          </div>
        ) : (
          <div className="non-host-actions">
            <div className="waiting-for-host">
              <div className="waiting-message">
                <FaClock />
                <h3>Ожидание хоста</h3>
                <p>Лобби начнется, когда хост запустит тест</p>
                <div className="host-info">
                  <span>Хост: {participants.find(p => p.id === lobby?.host_id)?.name || 'Unknown'}</span>
                </div>
              </div>
            </div>
            
            <div className="lobby-actions non-host">
              <button 
                className="action-btn leave-btn"
                onClick={handleLeaveLobby}
                disabled={loading}
              >
                <FaSignOutAlt />
                Выйти из лобби
              </button>
            </div>
          </div>
        )}
        </div>
      </div>
      
      {/* QR Code Modal */}
      {qrModalOpen && (
        <div className="qr-modal-overlay" onClick={() => setQrModalOpen(false)}>
          <div className="qr-modal" onClick={(e) => e.stopPropagation()}>
            <div className="qr-modal-header">
              <h3>QR-код для присоединения</h3>
              <button className="qr-modal-close" onClick={() => setQrModalOpen(false)}>
                <FaTimes />
              </button>
            </div>
            <div className="qr-modal-content">
              {qrCodeUrl && (
                <img src={qrCodeUrl} alt="QR Code" className="qr-code-large" />
              )}
              <p>Отсканируйте QR-код для присоединения к лобби</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LobbyWaitingPage; 