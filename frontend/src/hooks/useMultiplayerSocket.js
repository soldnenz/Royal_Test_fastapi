import { useState, useEffect, useRef, useCallback } from 'react';
import { io } from 'socket.io-client';

const useMultiplayerSocket = (
  lobbyId, 
  onUserEvent, 
  onError, 
  onKicked, 
  onLobbyClosed, 
  onLobbyStarted,
  onParticipantAnswered,
  onCorrectAnswerShown,
  onNextQuestion,
  onTestFinished,
  onParticipantAnswerDetails
) => {
  const [isConnected, setIsConnected] = useState(false);
  const [onlineUsers, setOnlineUsers] = useState([]);
  const socketRef = useRef(null);

  const connect = useCallback(() => {
    console.log('Attempting to connect to WebSocket, lobbyId:', lobbyId, 'already connected:', socketRef.current?.connected, 'stack trace:', new Error().stack);
    if (!lobbyId || socketRef.current?.connected) return;

    const wsToken = localStorage.getItem('ws_token');
    if (!wsToken) {
      console.error('No WS token found in localStorage');
      if(onError) onError("Ошибка аутентификации WS");
      return;
    }

    try {
      // Подключаемся к неймспейсу /ws
      const socket = io(`${window.location.origin}/ws`, {
        path: '/socket.io/',
        auth: { token: wsToken }
      });

      socketRef.current = socket;

      socket.on('connect', () => {
        console.log('Socket.IO connected, sending join_lobby event to /ws namespace.');
        setIsConnected(true);
        socket.emit('join_lobby', { lobby_id: lobbyId });
      });

      socket.on('disconnect', (reason) => {
        console.log('Socket.IO disconnected:', reason, 'lobbyId:', lobbyId);
        setIsConnected(false);
        setOnlineUsers([]);
      });
      
      socket.on('connect_error', (error) => {
        console.error('Socket.IO connection error:', error.message);
        setIsConnected(false);
        if (error.message.includes('Auth failed')) {
            localStorage.removeItem('ws_token');
            if (onError) {
                onError('Ошибка авторизации. Пожалуйста, попробуйте войти в лобби заново.');
            }
        }
      });
      
      // Глобальный обработчик ошибок от сервера
      socket.on('error', (data) => {
        console.error('Received server error:', data.message);
        if (onError) {
          onError(data.message || 'Произошла ошибка на сервере.');
        }
      });

      // --- Обновленная логика обработки событий ---

      socket.on('user_joined', (data) => {
        console.log('Event: user_joined', data);
        const { user_id } = data;
        // Немедленно добавляем пользователя в onlineUsers
        if (user_id) {
          console.log('Adding user to onlineUsers:', user_id);
          setOnlineUsers(prev => {
            if (!prev.includes(user_id)) {
              const newOnlineUsers = [...prev, user_id];
              console.log('Updated onlineUsers (joined):', newOnlineUsers);
              return newOnlineUsers;
            }
            console.log('User already in onlineUsers:', user_id);
            return prev;
          });
        }
        if (onUserEvent) onUserEvent('join');
      });

      socket.on('user_left', (data) => {
        console.log('Event: user_left', data);
        const { user_id } = data;
        // Немедленно убираем пользователя из onlineUsers
        if (user_id) {
          console.log('Removing user from onlineUsers:', user_id);
          setOnlineUsers(prev => {
            console.log('Previous onlineUsers:', prev);
            const newOnlineUsers = prev.filter(id => id !== user_id);
            console.log('Updated onlineUsers (left):', newOnlineUsers);
            return newOnlineUsers;
          });
        }
        if (onUserEvent) onUserEvent('leave');
      });

      socket.on('online_status_update', (data) => {
        console.log('Event: online_status_update', data);
        if (data && Array.isArray(data.online_users)) {
          console.log('Setting onlineUsers from server:', data.online_users);
          setOnlineUsers(data.online_users);
        }
      });

      socket.on('kicked', (data) => {
        console.log('Event: kicked', data);
        if (onKicked) onKicked(data.reason || 'Вы были исключены хостом.');
        disconnect();
      });

      socket.on('lobby_closed', (data) => {
        console.log('Event: lobby_closed', data);
        if (onLobbyClosed) onLobbyClosed('Лобби было закрыто хостом.');
        disconnect();
      });

      socket.on('lobby_started', (data) => {
        console.log('Event: lobby_started', data);
        if (onLobbyStarted) onLobbyStarted(data);
      });

      socket.on('participant_answered', (data) => {
        console.log('Event: participant_answered', data);
        if (onParticipantAnswered) onParticipantAnswered(data);
      });

      socket.on('correct_answer_shown', (data) => {
        console.log('Event: correct_answer_shown', data);
        if (onCorrectAnswerShown) onCorrectAnswerShown(data);
      });

      socket.on('next_question', (data) => {
        console.log('Event: next_question', data);
        if (onNextQuestion) onNextQuestion(data);
      });

      socket.on('test_finished', (data) => {
        console.log('Event: test_finished', data);
        if (onTestFinished) onTestFinished(data);
      });

      socket.on('participant_answer_details', (data) => {
        console.log('Event: participant_answer_details', data);
        if (onParticipantAnswerDetails) onParticipantAnswerDetails(data);
      });
      
    } catch (error) {
      console.error('Error creating Socket.IO connection:', error);
    }
  }, [lobbyId]); // Убираем все колбэки из зависимостей

  const disconnect = useCallback(() => {
    console.log('Disconnecting WebSocket, socketRef.current:', !!socketRef.current);
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
    setIsConnected(false);
    setOnlineUsers([]);
  }, []);

  // Функция для отправки событий на сервер
  const sendEvent = useCallback((eventName, payload) => {
    if (socketRef.current && socketRef.current.connected) {
      console.log(`Sending event '${eventName}' with payload:`, payload);
      socketRef.current.emit(eventName, payload);
    } else {
      console.error(`Socket not connected. Cannot send event '${eventName}'.`);
      if(onError) onError("Нет подключения к серверу для отправки события.");
    }
  }, [onError]);


  useEffect(() => {
    // Убираем reconnect-логику, т.к. socket.io делает это автоматически
    console.log('useMultiplayerSocket useEffect triggered, lobbyId:', lobbyId);
    if (lobbyId) {
      connect();
    }
    return () => {
      console.log('useMultiplayerSocket cleanup, disconnecting...');
      disconnect();
    };
  }, [lobbyId, connect, disconnect]);

  return {
    isConnected,
    onlineUsers,
    sendEvent, // <-- Экспортируем новую функцию
    disconnect // <-- Экспортируем для явного выхода
  };
};

export default useMultiplayerSocket; 