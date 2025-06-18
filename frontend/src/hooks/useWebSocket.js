import { useRef, useEffect, useCallback, useState } from 'react';
import api from '../utils/axios';

const useWebSocket = (url, options = {}) => {
  const {
    onOpen,
    onMessage,
    onClose,
    onError,
    onReconnect,
    maxReconnectAttempts = 5,
    reconnectDelay = 1000,
    maxReconnectDelay = 30000,
    autoReconnect = true,
    heartbeatInterval = 30000
  } = options;

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const heartbeatIntervalRef = useRef(null);
  const mountedRef = useRef(true);

  const [isConnected, setIsConnected] = useState(false);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [connectionState, setConnectionState] = useState('disconnected'); // 'connecting', 'connected', 'disconnected', 'error'

  // Calculate reconnect delay with exponential backoff
  const getReconnectDelay = useCallback((attempts) => {
    return Math.min(reconnectDelay * Math.pow(2, attempts), maxReconnectDelay);
  }, [reconnectDelay, maxReconnectDelay]);

  // Clear all timers
  const clearTimers = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  // Send heartbeat
  const sendHeartbeat = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type: 'heartbeat' }));
      } catch (error) {
        console.error('Failed to send heartbeat:', error);
      }
    }
  }, []);

  // Start heartbeat
  const startHeartbeat = useCallback(() => {
    if (heartbeatInterval > 0) {
      heartbeatIntervalRef.current = setInterval(sendHeartbeat, heartbeatInterval);
    }
  }, [heartbeatInterval, sendHeartbeat]);

  // Stop heartbeat
  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  // Connect to WebSocket
  const connect = useCallback(async (isReconnect = false) => {
    if (!mountedRef.current) return;

    try {
      setConnectionState('connecting');
      clearTimers();

      // Close existing connection properly
      if (wsRef.current) {
        if (wsRef.current.readyState === WebSocket.CONNECTING) {
          // If still connecting, wait a bit and force close
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        if (wsRef.current.readyState !== WebSocket.CLOSED) {
          wsRef.current.close(1000, 'Creating new connection');
          // Wait for close to complete
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        wsRef.current = null;
      }

      if (!url) {
        throw new Error('WebSocket URL is required');
      }

      console.log(`${isReconnect ? 'Reconnecting' : 'Connecting'} to WebSocket:`, url);
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = (event) => {
        if (!mountedRef.current) return;
        
        console.log('WebSocket connected successfully');
        setIsConnected(true);
        setConnectionState('connected');
        reconnectAttemptsRef.current = 0;
        setReconnectAttempts(0);
        
        startHeartbeat();
        
        if (onOpen) {
          onOpen(event);
        }
      };

      wsRef.current.onmessage = (event) => {
        if (!mountedRef.current) return;

        try {
          let data;
          
          // Check if message is JSON
          if (typeof event.data === 'string') {
            try {
              data = JSON.parse(event.data);
            } catch (parseError) {
              console.warn('Received non-JSON message:', event.data);
              if (onMessage) {
                onMessage(null, event, parseError);
              }
              return;
            }
          } else {
            data = event.data;
          }
          
          // Handle heartbeat internally
          if (data && data.type === 'heartbeat') {
            return;
          }

          if (onMessage) {
            onMessage(data, event);
          }
        } catch (error) {
          console.error('Error processing WebSocket message:', error);
          if (onMessage) {
            onMessage(null, event, error);
          }
        }
      };

      wsRef.current.onclose = (event) => {
        if (!mountedRef.current) return;

        console.log('WebSocket disconnected', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean
        });

        setIsConnected(false);
        setConnectionState('disconnected');
        stopHeartbeat();

        if (onClose) {
          onClose(event);
        }

        // Auto-reconnect logic
        if (autoReconnect && 
            event.code !== 1000 && 
            event.code !== 1001 && 
            reconnectAttemptsRef.current < maxReconnectAttempts) {
          
          const delay = getReconnectDelay(reconnectAttemptsRef.current);
          console.log(`Attempting to reconnect in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`);

          reconnectTimeoutRef.current = setTimeout(async () => {
            if (mountedRef.current) {
              reconnectAttemptsRef.current++;
              setReconnectAttempts(reconnectAttemptsRef.current);
              
              // Call onReconnect if provided to refresh token/URL
              if (onReconnect) {
                try {
                  await onReconnect();
                  // Wait longer for the URL to be updated
                  await new Promise(resolve => setTimeout(resolve, 200));
                } catch (error) {
                  console.error('Error in onReconnect callback:', error);
                }
              }
              
              // Additional wait to ensure URL is updated
              setTimeout(() => {
                if (mountedRef.current) {
                  connect(true);
                }
              }, 300);
            }
          }, delay);
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.log('Max reconnection attempts reached');
          setConnectionState('error');
        }
      };

      wsRef.current.onerror = (error) => {
        if (!mountedRef.current) return;

        console.error('WebSocket error:', error);
        setIsConnected(false);
        setConnectionState('error');
        
        if (onError) {
          onError(error);
        }

        // Retry connection if we haven't exceeded max attempts
        if (autoReconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = getReconnectDelay(reconnectAttemptsRef.current);
          console.log(`Retrying WebSocket connection in ${delay}ms due to error`);

          reconnectTimeoutRef.current = setTimeout(async () => {
            if (mountedRef.current) {
              reconnectAttemptsRef.current++;
              setReconnectAttempts(reconnectAttemptsRef.current);
              
              // Call onReconnect if provided to refresh token/URL
              if (onReconnect) {
                try {
                  await onReconnect();
                  // Wait longer for the URL to be updated
                  await new Promise(resolve => setTimeout(resolve, 200));
                } catch (error) {
                  console.error('Error in onReconnect callback:', error);
                }
              }
              
              // Additional wait to ensure URL is updated
              setTimeout(() => {
                if (mountedRef.current) {
                  connect(true);
                }
              }, 300);
            }
          }, delay);
        }
      };

    } catch (error) {
      console.error('Error setting up WebSocket:', error);
      setConnectionState('error');
      
      if (onError) {
        onError(error);
      }

      // Retry connection
      if (autoReconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
        const delay = getReconnectDelay(reconnectAttemptsRef.current);
        console.log(`Retrying WebSocket connection in ${delay}ms due to setup error`);

        reconnectTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) {
            reconnectAttemptsRef.current++;
            setReconnectAttempts(reconnectAttemptsRef.current);
            connect(true);
          }
        }, delay);
      }
    }
  }, [url, onOpen, onMessage, onClose, onError, autoReconnect, maxReconnectAttempts, getReconnectDelay, startHeartbeat, stopHeartbeat, clearTimers]);

  // Disconnect WebSocket
  const disconnect = useCallback((code = 1000, reason = 'Client disconnect') => {
    clearTimers();
    stopHeartbeat();
    
    if (wsRef.current) {
      wsRef.current.close(code, reason);
      wsRef.current = null;
    }
    
    setIsConnected(false);
    setConnectionState('disconnected');
    reconnectAttemptsRef.current = 0;
    setReconnectAttempts(0);
  }, [clearTimers, stopHeartbeat]);

  // Send message
  const sendMessage = useCallback((message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        const messageStr = typeof message === 'string' ? message : JSON.stringify(message);
        wsRef.current.send(messageStr);
        return true;
      } catch (error) {
        console.error('Failed to send WebSocket message:', error);
        return false;
      }
    }
    return false;
  }, []);

  // Manual reconnect
  const reconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    setReconnectAttempts(0);
    connect(true);
  }, [connect]);

  // Handle visibility change
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        console.log('Page became visible, checking WebSocket connection');
        if (!isConnected && autoReconnect && url) {
          console.log('Attempting to reconnect WebSocket after page became visible');
          reconnect();
        }
      }
    };

    const handleWindowFocus = () => {
      console.log('Window gained focus, checking WebSocket connection');
      if (!isConnected && autoReconnect && url) {
        console.log('Attempting to reconnect WebSocket after window focus');
        setTimeout(() => reconnect(), 500);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleWindowFocus);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleWindowFocus);
    };
  }, [isConnected, autoReconnect, url, reconnect]);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    
    return () => {
      mountedRef.current = false;
      clearTimers();
      stopHeartbeat();
      
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting');
      }
    };
  }, [clearTimers, stopHeartbeat]);

  return {
    isConnected,
    connectionState,
    reconnectAttempts,
    connect,
    disconnect,
    sendMessage,
    reconnect
  };
};

export default useWebSocket; 