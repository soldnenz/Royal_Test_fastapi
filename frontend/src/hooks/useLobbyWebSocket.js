import { useCallback, useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { notify } from '../components/notifications/NotificationSystem';
import useWebSocket from './useWebSocket';
import api from '../utils/axios';
import { getTranslation } from '../utils/languageUtil';

const useLobbyWebSocket = (lobbyId, options = {}) => {
  const {
    onParticipantsUpdate,
    onLobbyUpdate,
    onError: onExternalError,
    ...wsOptions
  } = options;

  const navigate = useNavigate();
  const [wsUrl, setWsUrl] = useState(null);
  const [participants, setParticipants] = useState([]);
  const disconnectRef = useRef(null);
  const isConnectingRef = useRef(false);
  const manualReconnectRef = useRef(null);
  const tokenRequestRef = useRef(null);
  const initializedRef = useRef(false);

  // WebSocket event handlers
  const handleUserJoined = useCallback((data) => {
    console.log('User joined:', data);
    const { user_id, user_name, is_host } = data;

    // Не добавляем участников без имени или с некорректными данными
    if (!user_id || !user_name || user_name === 'Unknown User' || typeof user_name !== 'string' || user_name.trim() === '') {
      console.log('Skipping invalid participant:', data);
      return;
    }

    setParticipants(prevParticipants => {
      const exists = prevParticipants.some(p => p.id === user_id);
      
      if (exists) {
        // Обновляем существующего участника
        const updatedParticipants = prevParticipants.map(participant =>
          participant.id === user_id
            ? { ...participant, online: true, name: user_name, is_host }
            : participant
        );
        if (onParticipantsUpdate) {
          onParticipantsUpdate(updatedParticipants);
        }
        return updatedParticipants;
      } else {
        // Добавляем нового участника
        console.log('Adding new participant:', user_name);
        
        // Уведомление о присоединении
        notify.multiplayer(`${user_name} ${getTranslation('joinedTheLobby') || 'joined the lobby'}`, {
          title: '🎭 Новый участник'
        });

        const newParticipants = [...prevParticipants, {
          id: user_id,
          name: user_name || 'Unknown User',
          online: true,
          is_host: is_host || false
        }];

        if (onParticipantsUpdate) {
          onParticipantsUpdate(newParticipants);
        }
        return newParticipants;
      }
    });
  }, [onParticipantsUpdate]);

  const handleUserLeft = useCallback((data) => {
    console.log('User left:', data);
    const { user_id, user_name } = data;

    setParticipants(prevParticipants => {
      const leavingParticipant = prevParticipants.find(p => p.id === user_id);
      
      if (leavingParticipant) {
        // Уведомление о выходе участника
        const participantName = user_name || leavingParticipant.name;
        notify.warning(`${participantName} ${getTranslation('leftTheLobby') || 'left the lobby'}`, {
          title: '👋 Участник покинул лобби'
        });
      }

      const newParticipants = prevParticipants.filter(participant => participant.id !== user_id);
      if (onParticipantsUpdate) {
        onParticipantsUpdate(newParticipants);
      }
      return newParticipants;
    });
  }, [onParticipantsUpdate]);

  const handleUserStatusUpdate = useCallback((data) => {
    console.log('User status update:', data);
    const { user_id, status, user_name } = data;

    setParticipants(prevParticipants => {
      let newParticipants = prevParticipants.map(participant => {
        if (participant.id === user_id) {
          return {
            ...participant,
            online: status === 'joined' || status === 'online',
            name: user_name || participant.name
          };
        }
        return participant;
      });

      // Если пользователь присоединился, но его нет в списке, добавляем
      if (status === 'joined') {
        const exists = newParticipants.some(p => p.id === user_id);
        if (!exists) {
          newParticipants = [...newParticipants, {
            id: user_id,
            name: user_name || 'Unknown User',
            online: true
          }];
        }
      }

      // Если пользователь покинул лобби, удаляем его из списка
      if (status === 'left') {
        newParticipants = newParticipants.filter(participant => participant.id !== user_id);
      }

      if (onParticipantsUpdate) {
        onParticipantsUpdate(newParticipants);
      }
      return newParticipants;
    });
  }, [onParticipantsUpdate]);

  const handleParticipantsUpdated = useCallback(async (data) => {
    console.log('Participants updated:', data);

    if (data.participants) {
      const currentParticipantIds = participants.map(p => p.id);
      const newParticipantIds = data.participants.filter(id => !currentParticipantIds.includes(id));

      if (newParticipantIds.length === 0) {
        const updatedParticipants = participants.filter(p => data.participants.includes(p.id));
        setParticipants(updatedParticipants);
        if (onParticipantsUpdate) {
          onParticipantsUpdate(updatedParticipants);
        }
        return;
      }

      // Загружаем информацию только о новых участниках
      try {
        const newParticipantPromises = newParticipantIds.map(async (userId) => {
          try {
            const userResponse = await api.get(`/users/${userId}`);
            return {
              id: userId,
              name: userResponse.data.data?.full_name || 'Unknown User',
              online: true
            };
          } catch (error) {
            console.error(`Failed to fetch user ${userId}:`, error);
            return {
              id: userId,
              name: 'Unknown User',
              online: true
            };
          }
        });

        const newParticipantDetails = await Promise.all(newParticipantPromises);
        const existingParticipants = participants.filter(p => data.participants.includes(p.id));
        const allParticipants = [...existingParticipants, ...newParticipantDetails];

        setParticipants(allParticipants);
        if (onParticipantsUpdate) {
          onParticipantsUpdate(allParticipants);
        }
      } catch (error) {
        console.error('Error fetching participant details:', error);
      }
    }
  }, [participants, onParticipantsUpdate]);

  const handleLobbyUpdated = useCallback((data) => {
    console.log('Lobby updated:', data);
    if (onLobbyUpdate) {
      onLobbyUpdate(data);
    }
  }, [onLobbyUpdate]);

  const handleTestStarted = useCallback((data) => {
    console.log('Test started:', data);
    navigate(`/multiplayer/test/${lobbyId}`);
  }, [lobbyId, navigate]);

  const handleLobbyClosed = useCallback((data) => {
    console.log('Lobby closed:', data);
    
    // Clean up WebSocket connection
    if (disconnectRef.current) {
      disconnectRef.current(1000, 'Lobby closed');
    }

    // Show message and redirect
    if (onExternalError) {
      onExternalError(data.message || 'Лобби было закрыто');
    }

    const redirectDelay = data.redirect ? 1000 : 2000;
    setTimeout(() => {
      navigate('/dashboard', { replace: true });
    }, redirectDelay);
  }, [disconnectRef, navigate, onExternalError]);

  const handleWebSocketMessage = useCallback((data, event, error) => {
    if (error) {
      console.error('Error parsing WebSocket message:', error);
      return;
    }

    if (!data) return;

    console.log('WebSocket message received:', data);
    console.log('Message type:', data.type);
    console.log('Message data:', data.data);

    switch (data.type) {
      case 'user_joined':
        handleUserJoined(data.data);
        break;
      case 'user_left':
        handleUserLeft(data.data);
        break;
      case 'user_status_update':
        handleUserStatusUpdate(data.data);
        break;
      case 'participants_updated':
        handleParticipantsUpdated(data.data);
        break;
      case 'lobby_updated':
        handleLobbyUpdated(data.data);
        break;
      case 'test_started':
        handleTestStarted(data.data);
        break;
      case 'lobby_closed':
        handleLobbyClosed(data.data);
        break;
      case 'current_question':
        // Тест уже начался, перенаправляем на страницу мультиплеерного теста
        console.log('Test already in progress, redirecting to multiplayer test page');
        navigate(`/multiplayer/test/${lobbyId}`);
        break;
      case 'answered_users':
        // Информация о том, кто уже ответил (для хоста)
        console.log('Answered users update:', data.data);
        break;
      case 'next_question':
        // Переход к следующему вопросу
        console.log('Next question:', data.data);
        break;
      case 'test_finished':
        // Тест завершен
        console.log('Test finished:', data.data);
        break;
      case 'participant_answered':
        // Участник ответил на вопрос
        console.log('Participant answered:', data.data);
        break;
      case 'answer_received':
        // Ответ получен и обработан
        console.log('Answer received:', data.data);
        break;
      case 'show_correct_answer':
        // Показать правильный ответ
        console.log('Show correct answer:', data.data);
        break;
      case 'toggle_participant_answers':
        // Переключить видимость ответов участников
        console.log('Toggle participant answers:', data.data);
        break;
      case 'participant_left':
        // Участник покинул лобби
        console.log('Participant left:', data.data);
        handleUserLeft(data.data);
        break;
      case 'user_kicked':
        // Пользователь исключен из лобби
        console.log('User kicked:', data.data);
        
        // Уведомление об исключении
        notify.error('Вы были исключены из лобби', {
          title: '❌ Исключение'
        });

        // Перенаправляем на главную
        setTimeout(() => {
          navigate('/dashboard');
        }, 2000);
        break;
      case 'participant_kicked':
        // Участник исключен из лобби
        console.log('Participant kicked:', data.data);
        handleUserLeft(data.data);
        break;
      default:
        console.log('Unknown message type:', data.type);
    }
  }, [lobbyId, navigate, handleUserJoined, handleUserLeft, handleUserStatusUpdate, handleParticipantsUpdated, handleLobbyUpdated, handleTestStarted, handleLobbyClosed]);

  const handleWebSocketError = useCallback((error) => {
    console.error('WebSocket error:', error);
    if (onExternalError) {
      onExternalError('Соединение потеряно. Обновите страницу для переподключения.');
    }
    
    // Attempt to reconnect with fresh token after error
    setTimeout(() => {
      if (manualReconnectRef.current && !isConnectingRef.current) {
        manualReconnectRef.current();
      }
    }, 2000);
  }, [onExternalError]);

  const handleWebSocketClose = useCallback((event) => {
    console.log('WebSocket closed:', event);
    
    // If connection was closed unexpectedly (not a clean close), try to reconnect
    if (event.code !== 1000 && event.code !== 1001) {
      console.log('Connection closed unexpectedly, attempting to reconnect...');
      setTimeout(() => {
        if (manualReconnectRef.current && !isConnectingRef.current) {
          manualReconnectRef.current();
        }
      }, 1000);
    }
  }, []);

  // Initialize WebSocket with token
  const initializeWebSocket = useCallback(async () => {
    // Предотвращаем множественные запросы токенов
    if (tokenRequestRef.current) {
      console.log('Token request already in progress, waiting...');
      return tokenRequestRef.current;
    }

    console.log('Initializing WebSocket connection...');

    tokenRequestRef.current = (async () => {
      try {
        const tokenResponse = await api.get('/websocket_token/ws-token');
        if (tokenResponse.data.status !== 'ok') {
          throw new Error('Failed to get WebSocket token');
        }

        const wsToken = tokenResponse.data.data.token;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}/api/ws/lobby/${lobbyId}?token=${wsToken}`;
        
        console.log('Setting new WebSocket URL:', url);
        setWsUrl(url);
        return url;
      } catch (error) {
        console.error('Error initializing WebSocket:', error);
        if (onExternalError) {
          onExternalError('Не удалось подключиться к серверу');
        }
        throw error;
      } finally {
        tokenRequestRef.current = null;
      }
    })();

    return tokenRequestRef.current;
  }, [lobbyId, onExternalError]);

  // Use base WebSocket hook
  const {
    isConnected,
    connectionState,
    reconnectAttempts,
    connect,
    disconnect,
    sendMessage,
    reconnect
  } = useWebSocket(wsUrl, {
    onMessage: handleWebSocketMessage,
    onError: handleWebSocketError,
    onClose: handleWebSocketClose,
    maxReconnectAttempts: 5,
    autoReconnect: false, // Disable auto-reconnect, we'll handle it manually
    ...wsOptions
  });

  // Store disconnect function in ref to avoid circular dependency
  useEffect(() => {
    disconnectRef.current = disconnect;
  }, [disconnect]);

  // Manual reconnect with fresh token
  const manualReconnect = useCallback(async () => {
    if (isConnectingRef.current) {
      console.log('Already connecting, skipping duplicate reconnect attempt');
      return;
    }
    
    isConnectingRef.current = true;
    console.log('Manual reconnect: getting fresh token...');
    
    try {
      // Get fresh token and URL
      await initializeWebSocket();
      
      // Wait for URL to update
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Attempt connection
      connect();
    } catch (error) {
      console.error('Error during manual reconnect:', error);
    } finally {
      // Reset flag after a delay
      setTimeout(() => {
        isConnectingRef.current = false;
      }, 2000);
    }
  }, [initializeWebSocket, connect]);

  // Store manual reconnect function in ref
  useEffect(() => {
    manualReconnectRef.current = manualReconnect;
  }, [manualReconnect]);

  // Initialize WebSocket URL when lobbyId changes (only once)
  useEffect(() => {
    if (lobbyId && !initializedRef.current) {
      console.log('Initializing WebSocket for lobby:', lobbyId);
      initializedRef.current = true;
      initializeWebSocket();
    }

    // Cleanup function
    return () => {
      if (!lobbyId) {
        initializedRef.current = false;
        tokenRequestRef.current = null;
      }
    };
  }, [lobbyId, initializeWebSocket]);

  // Connect when URL is ready (with debounce)
  useEffect(() => {
    if (!wsUrl || isConnectingRef.current) return;

    const connectTimer = setTimeout(() => {
      if (wsUrl && !isConnected && !isConnectingRef.current) {
        console.log('Connecting to WebSocket with URL:', wsUrl);
        isConnectingRef.current = true;
        connect();
        
        // Reset connecting flag after connection attempt
        setTimeout(() => {
          isConnectingRef.current = false;
        }, 5000);
      }
    }, 100);

    return () => clearTimeout(connectTimer);
  }, [wsUrl, connect, isConnected]);

  // Update participants status periodically
  const updateParticipantsStatus = useCallback(async () => {
    if (!lobbyId || !isConnected) return;

    // Временно отключаем этот вызов API, так как WebSocket предоставляет информацию об участниках
    // try {
    //   const response = await api.get(`/lobbies/lobbies/${lobbyId}/online-users`);
    //   if (response.data.status === 'ok') {
    //     const onlineUsers = response.data.data.online_users;
    //     const onlineUserIds = onlineUsers.map(user => user.user_id);

    //     setParticipants(prevParticipants => {
    //       const updatedParticipants = prevParticipants.map(participant => ({
    //         ...participant,
    //         online: onlineUserIds.includes(participant.id)
    //       }));

    //       if (onParticipantsUpdate) {
    //         onParticipantsUpdate(updatedParticipants);
    //       }
    //       return updatedParticipants;
    //     });
    //   }
    // } catch (error) {
    //   console.error('Error updating participants status:', error);
    // }
    
    console.log('Participants status update skipped - using WebSocket data');
  }, [lobbyId, isConnected, onParticipantsUpdate]);

  return {
    isConnected,
    connectionState,
    reconnectAttempts,
    participants,
    connect: () => manualReconnectRef.current?.(),
    disconnect,
    sendMessage,
    reconnect: () => manualReconnectRef.current?.(),
    updateParticipantsStatus,
    setParticipants
  };
};

export default useLobbyWebSocket; 