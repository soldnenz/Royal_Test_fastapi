import { useState, useEffect, useRef, useCallback } from 'react';
import { io } from 'socket.io-client';

const useMultiplayerSocket = (lobbyId, onUserEvent, onError, onKicked, onLobbyClosed, onLobbyStarted) => {
  const [isConnected, setIsConnected] = useState(false);
  const [onlineUsers, setOnlineUsers] = useState([]);
  const socketRef = useRef(null);

  const connect = useCallback(() => {
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
        console.log('Socket.IO disconnected:', reason);
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
        if (onUserEvent) onUserEvent('join');
      });

      socket.on('user_left', (data) => {
        console.log('Event: user_left', data);
        if (onUserEvent) onUserEvent('leave');
      });

      socket.on('online_status_update', (data) => {
        console.log('Event: online_status_update', data);
        if (data && Array.isArray(data.online_users)) {
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
      
    } catch (error) {
      console.error('Error creating Socket.IO connection:', error);
    }
  }, [lobbyId, onUserEvent, onError, onKicked, onLobbyClosed, onLobbyStarted]);

  const disconnect = useCallback(() => {
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
    if (lobbyId && onUserEvent) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [lobbyId, connect, disconnect, onUserEvent]);

  return {
    isConnected,
    onlineUsers,
    sendEvent, // <-- Экспортируем новую функцию
    disconnect // <-- Экспортируем для явного выхода
  };
};

export default useMultiplayerSocket; 