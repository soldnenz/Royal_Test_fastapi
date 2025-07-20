import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useLanguage } from '../../contexts/LanguageContext';
import { useTheme } from '../../contexts/ThemeContext';
import { translations } from '../../translations/translations';
import api from '../../utils/axios';
import QRCode from 'qrcode';
import LobbyHeader from '../../components/lobby/LobbyHeader';
import useMultiplayerSocket from '../../hooks/useMultiplayerSocket';
import { notify } from '../../components/notifications/NotificationSystem';
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
  FaCheck,
  FaUserPlus,
  FaQrcode
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
  const [participants, setParticipants] = useState([]); // <-- Храним полный список участников здесь
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [qrCodeUrl, setQrCodeUrl] = useState('');
  const [copySuccess, setCopySuccess] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const [userSubscription, setUserSubscription] = useState(null);
  const [subscriptionError, setSubscriptionError] = useState('');
  const [canJoinLobby, setCanJoinLobby] = useState(false);
  const [qrModalOpen, setQrModalOpen] = useState(false);
  const [currentUserId, setCurrentUserId] = useState(null);
  const [isGuest, setIsGuest] = useState(() => localStorage.getItem('isGuest') === 'true');
  const [guestNickname, setGuestNickname] = useState('');
  const [modalMessage, setModalMessage] = useState(null);
  // Удаляем состояние isCurrentUserHost
  // const [isCurrentUserHost, setIsCurrentUserHost] = useState(false);

  const timeLeftRef = useRef(0);

  useEffect(() => {
    const guestInfo = localStorage.getItem('guestInfo');
    if (guestInfo) {
      const { nickname } = JSON.parse(guestInfo);
      setGuestNickname(nickname);
    }
  }, []);

  // 1. Функция для получения списка участников по HTTP
  const fetchParticipants = useCallback(async () => {
    if (!lobbyId) return;
    try {
      const response = await api.get(`/multiplayer/lobbies/${lobbyId}/participants`);
      if (response.data.status === 'ok') {
        setParticipants(response.data.data.participants || []);
      }
    } catch (error) {
      console.error('Failed to fetch participants:', error);
      setError(t['failedToLoadParticipants'] || 'Не удалось загрузить участников');
    }
  }, [lobbyId, t]);

  // 2. Колбэк для сокета: при входе/выходе/кике пользователя, перезапрашиваем список
  const handleUserEvent = useCallback((event) => {
    console.log(`Socket event received: ${event}, fetching participants...`);
    // Обновляем список участников при любом событии (join, leave, kick)
    fetchParticipants();
  }, [fetchParticipants]);
  
  const handleSocketError = useCallback((errorMessage) => {
    console.error('Socket error:', errorMessage);
    // Показываем ошибку через систему уведомлений
    notify.error(errorMessage, {
      important: true,
      duration: 5000
    });
  }, []);

  const handleKicked = useCallback((reason) => {
    setModalMessage({
      title: 'Вы были исключены',
      message: reason,
      buttonText: 'Вернуться на главную',
      redirectPath: isGuest ? '/' : '/dashboard'
    });
  }, [isGuest]);

  const handleKickSuccess = useCallback((message) => {
    // Показываем уведомление хосту о том, что пользователь уже вышел
    notify.info(message || 'Пользователь уже вышел из лобби', {
      duration: 3000
    });
  }, []);

  const handleLobbyClosed = useCallback((reason) => {
    setModalMessage({
      title: 'Лобби закрыто',
      message: reason,
      buttonText: 'Вернуться в дашборд',
      redirectPath: isGuest ? '/' : '/dashboard'
    });
  }, [isGuest]);

  const handleLobbyStarted = useCallback((data) => {
    console.log('Lobby started event received:', data);
    // Немедленный переход на страницу теста
    navigate(`/multiplayer/test/${lobbyId}`);
  }, [navigate, lobbyId]);

  // 3. Инициализация сокета
  const { 
    isConnected: wsConnected, 
    onlineUsers, 
    sendEvent: sendSocketEvent, // <-- Получаем новую функцию
    disconnect: disconnectSocket 
  } = useMultiplayerSocket({
    lobbyId,
    onUserEvent: handleUserEvent,
    onSocketError: handleSocketError,
    onKicked: handleKicked,
    onLobbyClosed: handleLobbyClosed,
    onLobbyStarted: handleLobbyStarted,
    onKickSuccess: handleKickSuccess
  });

  // Отладочный лог для onlineUsers
  useEffect(() => {
    console.log('LobbyWaitingPage: onlineUsers changed:', onlineUsers);
  }, [onlineUsers]);

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

  // Первоначальная загрузка данных о лобби и участниках
  useEffect(() => {
    const initialize = async () => {
      setLoading(true);
      try {
        const [lobbyResponse] = await Promise.all([
          api.get(`/multiplayer/lobbies/${lobbyId}`),
          fetchParticipants()
        ]);
        
        if (lobbyResponse.data.status === 'ok') {
          const lobbyData = lobbyResponse.data.data;
          setLobby(lobbyData);
          // Логика установки времени и QR-кода остается здесь
        } else {
          setError(lobbyResponse.data.message || t['failedToLoadLobby']);
        }
      } catch (error) {
        setError(error.response?.data?.message || t['failedToLoadLobby']);
      } finally {
        setLoading(false);
      }
    };
    if (lobbyId) {
      initialize();
    }
  }, [lobbyId, fetchParticipants, t]);

  // Удаляем useEffect для определения хоста


  // Логика с таймером и QR-кодом, которая зависит от `lobby`
  useEffect(() => {
    if (!lobby) return;

    // Countdown timer
    let timeLeftSeconds = 0;
    if (lobby.remaining_seconds !== undefined) {
      timeLeftSeconds = Math.max(0, lobby.remaining_seconds);
    } else {
      try {
        let createdAtString = lobby.created_at;
        if (!createdAtString.endsWith('Z') && !createdAtString.includes('+')) {
          createdAtString += 'Z';
        }
        const createdAt = new Date(createdAtString);
        const expiresAt = new Date(createdAt.getTime() + 4 * 60 * 60 * 1000);
        const now = new Date();
        timeLeftSeconds = Math.max(0, Math.floor((expiresAt - now) / 1000));
      } catch (error) {
        timeLeftSeconds = 4 * 60 * 60;
      }
    }
    setTimeLeft(timeLeftSeconds);
    timeLeftRef.current = timeLeftSeconds;

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

    // QR Code generation
    const lobbyUrl = `${window.location.origin}/multiplayer/join/${lobbyId}`;
    generateQRCode(lobbyUrl);

    return () => clearInterval(timer);
  }, [lobby, lobbyId, isDark, navigate, t]);

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

  // Start test
  const handleStartTest = async () => {
    try {
      setLoading(true);
      
      // 1. Сначала отправляем HTTP запрос на обычный роутер старта
      const response = await api.post(`/multiplayer/lobbies/${lobbyId}/start`, {
        lobby_id: lobbyId
      });
      
      if (response.data.status === 'ok') {
        // 2. При успешном старте отправляем событие в сокет для уведомления всех участников
        sendSocketEvent('start_test', { lobby_id: lobbyId });
        
        // 3. Показываем успешное уведомление
        // Проверяем статус лобби для соответствующего сообщения
        if (lobby?.status === 'in_progress') {
          notify.info('Переход к тесту...', {
            duration: 2000
          });
        } else {
          notify.success('Тест запускается...', {
            duration: 2000
          });
        }
        
        // 4. Переход происходит по событию 'lobby_started' от сокета
        // НЕ добавляем setTimeout, так как переход должен быть только по WebSocket событию
      } else {
        // Показываем ошибку через систему уведомлений
        notify.error(response.data.message || t['failedToStartTest'] || 'Failed to start test', {
          important: true,
          duration: 5000
        });
      }
    } catch (error) {
      console.error('Error starting test:', error);
      // Показываем ошибку через систему уведомлений
      notify.error(error.response?.data?.message || t['failedToStartTest'] || 'Failed to start test', {
        important: true,
        duration: 5000
      });
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
      
      // 1. Сначала отправляем HTTP запрос на обычный роутер закрытия
      const response = await api.post(`/multiplayer/lobbies/${lobbyId}/close`);
      
      if (response.data.status === 'ok') {
        // 2. При успешном закрытии отправляем событие в сокет для уведомления всех участников
        sendSocketEvent('close_lobby', { lobby_id: lobbyId });
        
        // 3. Показываем успешное уведомление
        notify.success('Лобби закрывается...', {
          duration: 2000
        });
        
        // 4. Навигация произойдет по событию 'lobby_closed' от сокета
        // Убираем setTimeout, так как он может конфликтовать с WebSocket событием
      } else {
        // Показываем ошибку через систему уведомлений
        notify.error(response.data.message || t['failedToCloseLobby'] || 'Failed to close lobby', {
          important: true,
          duration: 5000
        });
      }
    } catch (error) {
      console.error('Error closing lobby:', error);
      // Показываем ошибку через систему уведомлений
      notify.error(error.response?.data?.message || t['failedToCloseLobby'] || 'Failed to close lobby', {
        important: true,
        duration: 5000
      });
    } finally {
      setLoading(false);
    }
  };

  // Обновляем функцию handleKickParticipant
  const handleKickParticipant = async (userId) => {
    console.log('handleKickParticipant called with userId:', userId);
    console.log('Current lobby state:', lobby);
    console.log('Is host?', lobby?.is_host);

    if (!lobby?.is_host) {
        console.log('Cannot kick - user is not host');
        return;
    }

    try {
        if (!window.confirm(t['confirmKickUser'] || 'Точно кикнуть этого пользователя?')) {
            console.log('Kick cancelled by user');
            return;
        }

        console.log('Sending kick request...');
        
        // 1. Сначала отправляем HTTP запрос
        const response = await api.post(`/multiplayer/lobbies/${lobbyId}/kick`, {
            target_user_id: userId
        });
        
        if (response.data.status === 'ok') {
            // 2. При успешном кике отправляем событие в сокет для уведомления
            sendSocketEvent('kick_user', { 
                lobby_id: lobbyId, 
                target_user_id: userId 
            });
            console.log('Kick successful');
            notify.success('Пользователь исключен.', {
              duration: 2000
            });
        } else {
            console.error('Kick failed:', response.data.message);
            // Показываем ошибку через систему уведомлений
            notify.error(response.data.message || t['failedToKickUser'] || 'Failed to kick user', {
              important: true,
              duration: 5000
            });
        }
    } catch (error) {
        console.error('Kick error:', error);
        // Показываем ошибку через систему уведомлений
        notify.error(error.response?.data?.message || t['failedToKickUser'] || 'Failed to kick user', {
          important: true,
          duration: 5000
        });
    }
  };

  // Leave lobby (guest)
  const handleGuestLeave = async (confirm = false) => {
    if (confirm && !window.confirm('Вы действительно хотите выйти из лобби?')) {
      return;
    }
    
    try {
      setLoading(true);
      
      // 1. Сначала отправляем HTTP запрос для удаления из базы данных
      const response = await api.post(`/multiplayer/lobbies/${lobbyId}/leave`);
      
      if (response.data.status === 'ok') {
        // 2. При успешном удалении из БД отправляем событие в сокет для уведомления других участников
        sendSocketEvent('leave_lobby', { 
          lobby_id: lobbyId, 
          user_id: currentUserId 
        });
        
        // 3. Показываем уведомление об успешном выходе
        notify.success('Вы вышли из лобби', {
          duration: 2000
        });
        
        // 4. Отключаем сокет
        disconnectSocket();
        
        // 5. Очищаем localStorage
        localStorage.removeItem('token');
        localStorage.removeItem('isGuest');
        localStorage.removeItem('ws_token');
        delete api.defaults.headers.common['Authorization'];
        
        // 6. Перенаправляем гостя на главную
        setTimeout(() => {
          navigate('/', { replace: true });
        }, 1000);
      } else {
        // Показываем ошибку через систему уведомлений
        notify.error(response.data.message || 'Не удалось выйти из лобби', {
          important: true,
          duration: 5000
        });
      }
    } catch (error) {
      console.error('Error leaving lobby:', error);
      // Показываем ошибку через систему уведомлений
      notify.error(error.response?.data?.message || 'Не удалось выйти из лобби', {
        important: true,
        duration: 5000
      });
    } finally {
      setLoading(false);
    }
  };

  // Leave lobby (non-host only)
  const handleLeaveLobby = async () => {
    if (!confirm('Вы действительно хотите выйти из лобби?')) {
      return;
    }
    
    try {
      // 1. Сначала отправляем HTTP запрос для удаления из базы данных
      const response = await api.post(`/multiplayer/lobbies/${lobbyId}/leave`);
      
      if (response.data.status === 'ok') {
        // 2. При успешном удалении из БД отправляем событие в сокет для уведомления других участников
        sendSocketEvent('leave_lobby', { 
          lobby_id: lobbyId, 
          user_id: currentUserId 
        });
        
        // 3. Показываем уведомление об успешном выходе
        notify.success('Вы вышли из лобби', {
          duration: 2000
        });
        
        // 4. Отключаем сокет
        disconnectSocket();
        
        // 5. Очищаем localStorage
        localStorage.removeItem('token');
        localStorage.removeItem('isGuest');
        localStorage.removeItem('ws_token');
        delete api.defaults.headers.common['Authorization'];
        
        // 6. Перенаправляем пользователя
        setTimeout(() => {
          navigate('/dashboard', { replace: true });
        }, 1000);
      } else {
        // Показываем ошибку через систему уведомлений
        notify.error(response.data.message || 'Не удалось выйти из лобби', {
          important: true,
          duration: 5000
        });
      }
    } catch (error) {
      console.error('Error leaving lobby:', error);
      // Показываем ошибку через систему уведомлений
      notify.error(error.response?.data?.message || 'Не удалось выйти из лобби', {
        important: true,
        duration: 5000
      });
    }
  };

  // Периодическое обновление статуса участников (убираем, так как теперь это делает Socket.IO)
  // useEffect(() => {
  //   if (!lobby || lobby.status !== 'waiting') return;
  //   
  //   // Обновляем статус каждые 15 секунд
  //   const statusInterval = setInterval(() => {
  //     updateParticipantsStatus();
  //   }, 15000);
  //   
  //   // Первое обновление сразу
  //   updateParticipantsStatus();
  //   
  //   return () => clearInterval(statusInterval);
  // }, [lobby, lobbyId, updateParticipantsStatus]);

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

  const isHost = lobby?.is_host === true; // Simplified check

  return (
    <div className={`lobby-waiting-page ${isDark ? 'dark-theme' : ''}`}>
      <LobbyHeader isGuest={isGuest} />
      
      <div className="main-content">
        <div className="lobby-container">
          {/* Lobby Header */}
          <div className="lobby-header">
            <div className="header-left">
              <button className="back-btn" onClick={() => isGuest ? handleGuestLeave() : navigate('/dashboard')}>
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
                    {t['connecting'] || 'Connecting...'}
                  </span>
                  {/* Убираем кнопку реконнекта, т.к. он автоматический */}
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
              {Array.isArray(participants) && participants.map((participant) => {
                const isOnline = onlineUsers.includes(participant.user_id);
                console.log(`Participant ${participant.name} (${participant.user_id}): ${isOnline ? 'ONLINE' : 'OFFLINE'}`);
                return (
                <div 
                  key={participant.user_id}
                  className={`participant-item ${!isOnline ? 'offline' : ''}`}
                >
                  <div className="participant-info">
                    <div className="participant-avatar">
                      {participant.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="participant-details">
                      <span className="participant-name">{participant.name}</span>
                      <span className="participant-status">
                        <div className={`status-dot ${isOnline ? 'online' : 'offline'}`}></div>
                        {participant.is_host ? (
                          <>
                            {lobby?.host_subscription_type === 'royal' ? <FaCrown /> : <FaGraduationCap />}
                            {t['host'] || 'Host'}
                          </>
                        ) : (
                          <>
                            {isOnline ? (t['online'] || 'Online') : (t['offline'] || 'Offline')}
                          </>
                        )}
                      </span>
                    </div>
                  </div>
                  
                  {lobby?.is_host && !participant.is_host && (
                    <button 
                        className="kick-btn"
                        onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('Kick button clicked for participant:', participant);
                            handleKickParticipant(participant.user_id);
                        }}
                        title={t['kickUser'] || 'Исключить пользователя'}
                    >
                        <FaTimes />
                    </button>
                  )}
                </div>
              )})}
              
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
        <div className="lobby-actions-container">
          {lobby?.is_host ? (
            <div className="lobby-actions host-actions">
              <button 
                className="action-btn start-btn"
                onClick={handleStartTest}
                disabled={loading || participants.length < 2 || !wsConnected}
              >
                <FaPlay />
                <span>{t['startTest'] || 'Начать тест'}</span>
                {loading && <div className="spinner"></div>}
              </button>
              <button 
                className="action-btn close-btn"
                onClick={handleCloseLobby}
                disabled={loading || !wsConnected} // Блокируем кнопку закрытия если нет связи
              >
                <FaTimes />
                <span>{t['closeLobby'] || 'Закрыть лобби'}</span>
              </button>
            </div>
          ) : (
            <div className="lobby-actions non-host-actions">
              <div className="waiting-for-host">
                <div className="waiting-message">
                  <FaClock />
                  <div className="waiting-text">
                    <h3>Ожидание хоста</h3>
                    <p>Тест начнется, когда хост его запустит</p>
                  </div>
                </div>
                <div className="host-info">
                  <span>Хост: <strong>{participants.find(p => p.is_host)?.name || lobby?.host_name || 'Unknown'}</strong></span>
                </div>
              </div>
              <button 
                className="action-btn leave-btn"
                onClick={() => isGuest ? handleGuestLeave(true) : handleLeaveLobby()}
                disabled={loading}
              >
                <FaSignOutAlt />
                <span>Выйти из лобби</span>
              </button>
            </div>
          )}
        </div>
        </div>
      </div>
      
      {/* Kick/Close Modal */}
      {modalMessage && (
        <div className="modal-overlay">
          <div className="modal-content">
            <FaExclamationTriangle className="modal-icon" />
            <h3>{modalMessage.title}</h3>
            <p>{modalMessage.message}</p>
            <button 
              onClick={() => navigate(modalMessage.redirectPath, { replace: true })}
              className="modal-button"
            >
              {modalMessage.buttonText}
            </button>
          </div>
        </div>
      )}
      
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