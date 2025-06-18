import { useCallback, useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import useWebSocket from './useWebSocket';
import api from '../utils/axios';
import { getTranslation } from '../utils/languageUtil';
import { notify } from '../components/notifications/NotificationSystem';

const useMultiplayerTestWebSocket = (lobbyId, callbacks = {}) => {
  const {
    onAnswerReceived,
    onNextQuestion,
    onShowCorrectAnswer,
    onToggleParticipantAnswers,
    onTestFinished,
    onParticipantAnswered,
    onError: onExternalError,
    ...wsOptions
  } = callbacks;

  const navigate = useNavigate();
  const [wsUrl, setWsUrl] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [showCorrectAnswer, setShowCorrectAnswer] = useState(false);
  const [showParticipantAnswers, setShowParticipantAnswers] = useState(false);
  const [testFinished, setTestFinished] = useState(false);
  const [participantAnswers, setParticipantAnswers] = useState({});
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  const [currentQuestionId, setCurrentQuestionId] = useState(null);
  const [lobbyStatus, setLobbyStatus] = useState('waiting');
  const [hostId, setHostId] = useState(null);
  const [isHost, setIsHost] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [lastPingTime, setLastPingTime] = useState(Date.now());
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [connectionId, setConnectionId] = useState(null);
  const [messageQueue, setMessageQueue] = useState([]);
  
  const disconnectRef = useRef(null);
  const isConnectingRef = useRef(false);
  const manualReconnectRef = useRef(null);
  const tokenRequestRef = useRef(null);
  const initializedRef = useRef(false);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const heartbeatTimeoutRef = useRef(null);

  // Handle participants list – moved up so it is defined before other callbacks use it
  const handleParticipantsList = useCallback((data) => {
    console.log('Received participants list:', data);
    const { participants } = data;

    if (!Array.isArray(participants)) return;

    const uniqueMap = new Map();

    participants.forEach(p => {
      // Validate basic fields
      const id = p.id || p.user_id;
      if (!id) return;

      const name = p.name || p.user_name || 'Unknown User';
      const online = p.online !== false;
      const is_host = p.is_host || false;

      // Skip obviously invalid names
      if (!name || name.trim() === '' || name === 'Unknown User') return;

      uniqueMap.set(id, { id, name, online, is_host });
    });

    // Merge with existing participants to preserve known names
    setParticipants(prev => {
      const merged = new Map();

      prev.forEach(p => {
        merged.set(p.id, { ...p });
      });

      uniqueMap.forEach((value, key) => {
        merged.set(key, { ...merged.get(key), ...value });
      });

      return Array.from(merged.values());
    });
  }, []);

  // WebSocket event handlers
  const handleAnswerReceived = useCallback((data) => {
    console.log('Answer received:', data);
    const { user_id, question_id, answer_index, is_correct } = data;
    
    // Обновляем состояние ответов участников с полной информацией
    setParticipantAnswers(prev => ({
      ...prev,
      [user_id]: {
        ...prev[user_id],
        [question_id]: { 
          answer_index: typeof answer_index === 'number' ? answer_index : null, 
          is_correct,
          answered: true,
          timestamp: new Date().toISOString()
        }
      }
    }));

    // Находим участника по ID для отображения имени
    const participant = participants.find(p => p.id === user_id);
    const participantName = participant ? participant.name : 'Участник';
    
    // Уведомление о получении ответа (только для других участников, не для себя)
    const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
    if (currentUser.id !== user_id) { // Не показываем свой собственный ответ
      // Для безопасности больше не показываем варианты ответов в уведомлениях
      notify.multiplayer(`${participantName} ответил`);
    }
  }, [participants]);

  const handleParticipantAnswered = useCallback((data) => {
    console.log('Participant answered:', data);
    const { user_id, question_id, answered } = data;
    
    // Обновляем статус ответа участника, но только если у нас еще нет детальной информации
    setParticipantAnswers(prev => {
      const existing = prev[user_id]?.[question_id];
      if (existing && existing.answer_index !== undefined) {
        // У нас уже есть детальная информация от answer_received, не перезаписываем
        return prev;
      }
      
      return {
        ...prev,
        [user_id]: {
          ...prev[user_id],
          [question_id]: { 
            answered: true,
            timestamp: new Date().toISOString()
          }
        }
      };
    });
  }, []);

  const handleQuestionStatus = useCallback((data) => {
    console.log('Question status:', data);
    const { question_id, answered_count, total_participants, can_advance } = data;
    
    // Можно добавить отображение статуса прогресса ответов для хоста
    // Например, показать сколько участников ответили
  }, []);

  const handleNextQuestion = useCallback((data) => {
    console.log('Next question:', data);
    const { question_id, question_index } = data;
    
    setCurrentQuestion({ question_id, question_index });
    setCurrentQuestionIndex(question_index);
    setShowCorrectAnswer(false); // Скрываем правильный ответ при переходе к новому вопросу
    
    // Уведомление о переходе к следующему вопросу
    notify.action(`${getTranslation('nextQuestion') || 'Next question'} ${(question_index || 0) + 1}`, {
      title: '📝 Следующий вопрос'
    });
    
    if (onNextQuestion) {
      onNextQuestion(data);
    }
  }, [onNextQuestion]);

  const handleCurrentQuestion = useCallback((data) => {
    console.log('Current question:', data);
    const { question_id, question_index } = data;
    
    setCurrentQuestion({ question_id, question_index });
    setCurrentQuestionIndex(question_index);
  }, []);

  const handleConnected = useCallback(() => {
    console.log('WebSocket connected, requesting current question sync');
    
    // Запрашиваем синхронизацию текущего вопроса при подключении
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'request_sync',
        data: {
          lobby_id: lobbyId,
          timestamp: Date.now()
        }
      }));
      
      // Также запрашиваем список участников
      setTimeout(() => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            type: 'request_participants',
            data: {
              lobby_id: lobbyId
            }
          }));
        }
      }, 500);
    }
  }, [lobbyId]);

  const handleShowCorrectAnswer = useCallback((data) => {
    console.log('Show correct answer:', data);
    const { question_id, correct_answer_index, explanation, has_after_media, after_answer_media_type } = data;
    
    setShowCorrectAnswer(true);
    
    // Уведомление о показе правильного ответа
    notify.answer('Правильный ответ показан всем участникам', {
      title: '✅ Ответ показан'
    });
    
    if (onShowCorrectAnswer) {
      onShowCorrectAnswer({
        question_id: String(question_id), // Приводим к строке для корректного сравнения
        correct_answer_index,
        explanation,
        has_after_media,
        after_answer_media_type
      });
    }
  }, [onShowCorrectAnswer]);

  const handleToggleParticipantAnswers = useCallback((data) => {
    console.log('Toggle participant answers:', data);
    const { show_answers } = data;
    
    setShowParticipantAnswers(show_answers);
    
    // Уведомление о переключении видимости ответов
    notify.info(`Ответы участников ${show_answers ? 'показаны' : 'скрыты'}`, {
      title: '👥 Управление ответами'
    });
    
    if (onToggleParticipantAnswers) {
      onToggleParticipantAnswers(data);
    }
  }, [onToggleParticipantAnswers]);

  const handleSyncResponse = useCallback((data) => {
    console.log('Sync response received:', data);
    const { current_question_index, current_question_id, lobby_status, participants, forced_sync } = data;
    
    if (typeof current_question_index === 'number' && current_question_index >= 0) {
      console.log(`Синхронизация через WebSocket: обновляем индекс на ${current_question_index}`);
      setCurrentQuestionIndex(current_question_index);
      setCurrentQuestionId(current_question_id);
      
      // При принудительной синхронизации показываем уведомление
      if (forced_sync) {
        notify.waiting('Состояние синхронизировано с сервером', {
          title: '🔄 Синхронизация'
        });
      }
      
      // Обновляем участников если они предоставлены
      if (Array.isArray(participants)) {
        console.log('Updating participants from sync response');
        handleParticipantsList({ participants });
      }
      
      // Уведомляем родительский компонент о необходимости синхронизации
      if (callbacks.onSync) {
        callbacks.onSync({
          question_index: current_question_index,
          question_id: current_question_id,
          forced_sync
        });
      }
    }
  }, [callbacks, handleParticipantsList]);

  const handleTestFinished = useCallback((data) => {
    console.log('Test finished:', data);
    setTestFinished(true);
    
    // Уведомление о завершении теста
    notify.success(getTranslation('testCompleted') || 'Test completed!', {
      title: '🎉 Тест завершен'
    });
    
    if (onTestFinished) {
      onTestFinished(data);
    }
  }, [onTestFinished]);

  const handleUserJoined = useCallback((data) => {
    console.log('User joined:', data);
    const { user_id, user_name, is_host } = data;
    
    // Проверяем, что участник не дублируется
    setParticipants(prevParticipants => {
      const existingIndex = prevParticipants.findIndex(p => p.id === user_id);
      if (existingIndex >= 0) {
        // Обновляем существующего участника
        const updatedParticipants = [...prevParticipants];
        updatedParticipants[existingIndex] = {
          ...updatedParticipants[existingIndex],
          name: user_name || updatedParticipants[existingIndex].name,
          online: true,
          is_host: is_host || false
        };
        return updatedParticipants;
      } else {
        // Добавляем нового участника
        const newParticipant = {
          id: user_id,
          name: user_name || 'Unknown User',
          online: true,
          is_host: is_host || false
        };
        console.log('Adding new participant:', newParticipant);
        return [...prevParticipants, newParticipant];
      }
    });
  }, []);

  const handleUserLeft = useCallback((data) => {
    console.log('User left:', data);
    const { user_id } = data;
    
    setParticipants(prevParticipants => 
      prevParticipants.filter(p => p.id !== user_id)
    );
  }, []);

  const handleLobbyClosed = useCallback((data) => {
    console.log('Lobby closed:', data);
    setTestFinished(true);
    
    // Уведомление о закрытии лобби
    notify.warning(getTranslation('lobbyClosed') || 'Lobby has been closed', {
      title: '⚠️ Лобби закрыто'
    });
    
    // Перенаправляем на страницу ожидания или дашборд
    setTimeout(() => {
      navigate('/dashboard');
    }, 3000);
  }, [navigate]);

  const handleUserKicked = useCallback((data) => {
    console.log('User kicked:', data);
    const { user_id, user_name } = data;
    
    // Удаляем участника из списка
    setParticipants(prevParticipants => 
      prevParticipants.filter(p => p.id !== user_id)
    );
    
    // Уведомление
    notify.warning(`${user_name || 'Участник'} был исключен из лобби`, {
      title: '👤 Участник исключен'
    });
  }, []);

  const handleParticipantKicked = useCallback((data) => {
    console.log('Participant kicked:', data);
    // Если исключили текущего пользователя, перенаправляем на дашборд
    const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
    if (data.user_id === currentUser.id) {
      notify.error('Вы были исключены из лобби', {
        title: '❌ Исключение'
      });
      setTimeout(() => {
        navigate('/dashboard');
      }, 2000);
    } else {
      handleUserKicked(data);
    }
  }, [navigate, handleUserKicked]);

  // Функция для получения ответа участника на текущий вопрос
  const getParticipantAnswerForQuestion = useCallback((participantId, questionId) => {
    if (!participantId || !questionId || !participantAnswers) return null;
    
    const userAnswers = participantAnswers[participantId];
    if (!userAnswers || typeof userAnswers !== 'object') return null;
    
    const answer = userAnswers[questionId];
    if (!answer || typeof answer !== 'object') return null;
    
    return typeof answer.answer_index === 'number' ? answer.answer_index : null;
  }, [participantAnswers]);

  // Функция для проверки, ответил ли участник на вопрос
  const hasParticipantAnswered = useCallback((participantId, questionId) => {
    if (!participantId || !questionId || !participantAnswers) return false;

    const userAnswers = participantAnswers[participantId];
    if (!userAnswers || typeof userAnswers !== 'object') return false;

    const answer = userAnswers[questionId];
    // Считаем, что участник ответил, если хранится индекс ответа ИЛИ флаг answered === true
    return !!(
      answer && typeof answer === 'object' && (
        'answer_index' in answer || answer.answered === true
      )
    );
  }, [participantAnswers]);

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
      case 'answer_received':
        console.log('Processing answer_received:', data.data);
        handleAnswerReceived(data.data);
        if (onAnswerReceived) {
          onAnswerReceived(data.data);
        }
        break;
      case 'participant_answered':
        handleParticipantAnswered(data.data);
        if (onParticipantAnswered) {
          onParticipantAnswered(data.data);
        }
        break;
      case 'next_question':
        console.log('Received next_question message:', data);
        if (onNextQuestion) {
          onNextQuestion(data.data);
        }
        break;
      case 'current_question':
        handleCurrentQuestion(data.data);
        break;
      case 'sync_response':
        handleSyncResponse(data.data);
        break;
      case 'show_correct_answer':
        console.log('Received show_correct_answer message:', data);
        if (onShowCorrectAnswer) {
          onShowCorrectAnswer(data.data);
        }
        break;
      case 'toggle_participant_answers':
        handleToggleParticipantAnswers(data.data);
        break;
      case 'test_finished':
        console.log('Test finished:', data.data);
        if (onTestFinished) {
          onTestFinished(data.data);
        } else {
          handleTestFinished(data.data);
        }
        break;
      case 'user_joined':
        handleUserJoined(data.data);
        break;
      case 'user_left':
      case 'participant_left':
      case 'user_kicked':
        handleUserLeft(data.data);
        break;
      case 'lobby_closed':
        handleLobbyClosed(data.data);
        break;
      case 'answered_users':
        // Информация о том, кто уже ответил (для хоста)
        console.log('Answered users update:', data.data);
        break;
      case 'participants_list':
      case 'lobby_participants':
        // Список участников лобби
        console.log('Participants list received:', data.data);
        handleParticipantsList(data.data);
        break;
      case 'host_next_question':
        // Хост перешел к следующему вопросу
        console.log('Host moved to next question:', data.data);
        notify.action(getTranslation('hostMovedToNextQuestion') || 'Host moved to next question', {
          title: '📝 Следующий вопрос'
        });
        break;
      case 'host_finish_test':
        // Хост завершил тест
        console.log('Host finished test:', data.data);
        notify.host(getTranslation('hostFinishedTest') || 'Host finished the test', {
          title: '🏁 Тест завершен'
        });
        if (onTestFinished) {
          onTestFinished(data.data);
        }
        break;
      case 'answer_submitted':
        // Участник отправил ответ
        console.log('Participant submitted answer:', data.data);
        const { user_id, question_id } = data.data;
        // Можно добавить логику для отображения статуса ответов участников
        break;
      case 'user_status_update':
        // Обновление статуса пользователя
        console.log('User status update:', data.data);
        const { user_id: statusUserId, status, user_name } = data.data;
        setParticipants(prevParticipants => 
          prevParticipants.map(participant =>
            participant.id === statusUserId
              ? { ...participant, online: status === 'online', name: user_name || participant.name }
              : participant
          )
        );
        break;
      case 'participants_updated':
        // Обновление списка участников (приходит только массив id)
        console.log('Participants updated:', data.data);
        if (Array.isArray(data.data.participants)) {
          handleParticipantsList({ participants: data.data.participants.map(id => ({ id })) });
        }
        break;
      case 'lobby_status':
        // Обновление статуса лобби
        console.log('Lobby status update:', data.data);
        const { status: lobbyStatus, current_index, show_participant_answers } = data.data;
        if (current_index !== undefined) {
          setCurrentQuestionIndex(current_index);
        }
        if (show_participant_answers !== undefined) {
          setShowParticipantAnswers(show_participant_answers);
        }
        break;
      case 'user_kicked':
        handleUserKicked(data.data);
        break;
      case 'participant_kicked':
        handleParticipantKicked(data.data);
        break;
      case 'question_status':
        handleQuestionStatus(data.data);
        break;
      default:
        console.log('Unknown message type:', data.type);
    }
  }, [
    handleAnswerReceived,
    handleParticipantAnswered,
    handleNextQuestion,
    handleCurrentQuestion,
    handleShowCorrectAnswer,
    handleToggleParticipantAnswers,
    handleTestFinished,
    handleUserJoined,
    handleUserLeft,
    handleLobbyClosed,
    handleUserKicked,
    handleParticipantKicked,
    onAnswerReceived,
    onParticipantAnswered,
    onNextQuestion,
    onShowCorrectAnswer,
    onTestFinished,
    handleParticipantsList,
    handleQuestionStatus
  ]);

  const handleWebSocketError = useCallback((error) => {
    console.error('WebSocket error:', error);
    
    // Уведомление об ошибке соединения
    notify.error(getTranslation('connectionLost') || 'Connection lost. Attempting to reconnect...', {
      title: '🔌 Потеря соединения'
    });
    
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
    isConnected: baseIsConnected,
    connectionState,
    reconnectAttempts: baseReconnectAttempts,
    connect,
    disconnect,
    sendMessage,
    reconnect,
    websocket
  } = useWebSocket(wsUrl, {
    onMessage: handleWebSocketMessage,
    onError: handleWebSocketError,
    onClose: handleWebSocketClose,
    onOpen: handleConnected,
    maxReconnectAttempts: 5,
    autoReconnect: false,
    ...wsOptions
  });

  // Store WebSocket reference
  useEffect(() => {
    wsRef.current = websocket;
  }, [websocket]);

  // Store disconnect function in ref
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
      await initializeWebSocket();
      await new Promise(resolve => setTimeout(resolve, 500));
      connect();
    } catch (error) {
      console.error('Error during manual reconnect:', error);
    } finally {
      setTimeout(() => {
        isConnectingRef.current = false;
      }, 2000);
    }
  }, [initializeWebSocket, connect]);

  // Store manual reconnect function in ref
  useEffect(() => {
    manualReconnectRef.current = manualReconnect;
  }, [manualReconnect]);

  // Initialize WebSocket URL when lobbyId changes
  useEffect(() => {
    if (lobbyId && !initializedRef.current) {
      console.log('Initializing WebSocket for multiplayer test:', lobbyId);
      initializedRef.current = true;
      initializeWebSocket();
    }

    return () => {
      if (!lobbyId) {
        initializedRef.current = false;
        tokenRequestRef.current = null;
      }
    };
  }, [lobbyId, initializeWebSocket]);

  // Connect when URL is ready
  useEffect(() => {
    if (!wsUrl || isConnectingRef.current) return;

    const connectTimer = setTimeout(() => {
      if (wsUrl && !baseIsConnected && !isConnectingRef.current) {
        console.log('Connecting to WebSocket with URL:', wsUrl);
        isConnectingRef.current = true;
        connect();
        
        setTimeout(() => {
          isConnectingRef.current = false;
        }, 5000);
      }
    }, 100);

    return () => clearTimeout(connectTimer);
  }, [wsUrl, connect, baseIsConnected]);

  // Request current question, lobby status and participants on connect
  useEffect(() => {
    if (baseIsConnected && sendMessage) {
      // Уведомление об успешном подключении
      if (baseReconnectAttempts > 0) {
        notify.success(getTranslation('reconnected') || 'Reconnected successfully!', {
          title: '🔌 Переподключение'
        });
      }
      
      // Запрашиваем синхронизацию (включает текущий вопрос и статус)
      sendMessage(JSON.stringify({
        type: 'request_sync',
        data: {
          timestamp: Date.now()
        }
      }));
      
      // Запрашиваем текущий вопрос (резервный запрос)
      sendMessage(JSON.stringify({
        type: 'request_current_question',
        data: {}
      }));
      
      // Запрашиваем статус лобби
      sendMessage(JSON.stringify({
        type: 'request_lobby_status',
        data: {}
      }));
      
      // Запрашиваем список участников
      sendMessage(JSON.stringify({
        type: 'request_participants',
        data: {}
      }));
      
      // Также загружаем участников через API для синхронизации
      const loadParticipants = async () => {
        try {
          const response = await api.get(`/lobbies/lobbies/${lobbyId}`);
          if (response.data.status === 'ok' && response.data.data.participants) {
            console.log('Loading initial participants from API:', response.data.data.participants);
            const validParticipants = response.data.data.participants
              .filter(p => {
                // Фильтруем участников с некорректными данными
                const hasValidId = p.id || p.user_id;
                const hasValidName = (p.name || p.user_name) && 
                                   (p.name || p.user_name) !== 'Unknown User' && 
                                   typeof (p.name || p.user_name) === 'string' &&
                                   (p.name || p.user_name).trim() !== '';
                
                return hasValidId && hasValidName;
              })
              .map(p => ({
                id: p.id || p.user_id,
                name: p.name || p.user_name,
                online: p.online !== false // Default to true unless explicitly false
              }));
            
            console.log('Setting filtered participants from API:', validParticipants);
            setParticipants(validParticipants);
          }
        } catch (error) {
          console.error('Error loading participants from API:', error);
        }
      };
      
      loadParticipants();
    }
  }, [baseIsConnected, sendMessage, lobbyId]);

  return {
    isConnected: baseIsConnected,
    connectionState,
    reconnectAttempts: baseReconnectAttempts,
    participants,
    currentQuestion,
    currentQuestionIndex,
    showCorrectAnswer,
    showParticipantAnswers,
    testFinished,
    participantAnswers,
    connect: initializeWebSocket,
    sendMessage,
    reconnect: manualReconnect,
    disconnect,
    getParticipantAnswerForQuestion,
    hasParticipantAnswered
  };
};

export default useMultiplayerTestWebSocket; 