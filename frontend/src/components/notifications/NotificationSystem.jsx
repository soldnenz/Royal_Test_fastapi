import React, { useState, useEffect, useCallback } from 'react';
import { 
  FaCheck, 
  FaTimes, 
  FaExclamationTriangle, 
  FaInfoCircle,
  FaUsers,
  FaCrown,
  FaArrowRight,
  FaLightbulb,
  FaFlag,
  FaClock
} from 'react-icons/fa';
import './NotificationSystem.css';

const NotificationSystem = () => {
  const [notifications, setNotifications] = useState([]);

  const removeNotification = useCallback((id) => {
    setNotifications(prev => prev.filter(notification => notification.id !== id));
  }, []);

  const addNotification = useCallback((notification) => {
    const id = Date.now() + Math.random();
    const newNotification = {
      id,
      ...notification,
      timestamp: Date.now()
    };

    setNotifications(prev => [...prev, newNotification]);

    // Auto remove after duration
    setTimeout(() => {
      removeNotification(id);
    }, notification.duration || 4000);

    return id;
  }, [removeNotification]);

  // Expose methods globally
  useEffect(() => {
    window.showNotification = addNotification;
    window.removeNotification = removeNotification;

    return () => {
      delete window.showNotification;
      delete window.removeNotification;
    };
  }, [addNotification, removeNotification]);

  const getNotificationIcon = (type, customIcon) => {
    if (customIcon) return customIcon;
    
    switch (type) {
      case 'success': return <FaCheck />;
      case 'error': return <FaTimes />;
      case 'warning': return <FaExclamationTriangle />;
      case 'info': return <FaInfoCircle />;
      case 'multiplayer': return <FaUsers />;
      case 'host': return <FaCrown />;
      case 'action': return <FaArrowRight />;
      case 'answer': return <FaLightbulb />;
      case 'finish': return <FaFlag />;
      case 'waiting': return <FaClock />;
      default: return <FaInfoCircle />;
    }
  };

  const getNotificationClass = (type) => {
    switch (type) {
      case 'success': return 'notification-success';
      case 'error': return 'notification-error';
      case 'warning': return 'notification-warning';
      case 'info': return 'notification-info';
      case 'multiplayer': return 'notification-multiplayer';
      case 'host': return 'notification-host';
      case 'action': return 'notification-action';
      case 'answer': return 'notification-answer';
      case 'finish': return 'notification-finish';
      case 'waiting': return 'notification-waiting';
      default: return 'notification-info';
    }
  };

  return (
    <div className="notification-container">
      {notifications.map((notification) => (
        <div
          key={notification.id}
          className={`notification ${getNotificationClass(notification.type)} ${
            notification.important ? 'notification-important' : ''
          }`}
          onClick={() => removeNotification(notification.id)}
        >
          <div className="notification-icon">
            {getNotificationIcon(notification.type, notification.icon)}
          </div>
          
          <div className="notification-content">
            {notification.title && (
              <div className="notification-title">{notification.title}</div>
            )}
            <div className="notification-message">{notification.message}</div>
          </div>
          
          <button
            className="notification-close"
            onClick={(e) => {
              e.stopPropagation();
              removeNotification(notification.id);
            }}
          >
            <FaTimes />
          </button>
        </div>
      ))}
    </div>
  );
};

// Helper functions for easy usage
export const notify = {
  success: (message, options = {}) => {
    if (window.showNotification) {
      return window.showNotification({
        type: 'success',
        message,
        duration: 3000,
        ...options
      });
    }
  },
  
  error: (message, options = {}) => {
    if (window.showNotification) {
      return window.showNotification({
        type: 'error',
        message,
        duration: 5000,
        ...options
      });
    }
  },
  
  warning: (message, options = {}) => {
    if (window.showNotification) {
      return window.showNotification({
        type: 'warning',
        message,
        duration: 4000,
        ...options
      });
    }
  },
  
  info: (message, options = {}) => {
    if (window.showNotification) {
      return window.showNotification({
        type: 'info',
        message,
        duration: 3000,
        ...options
      });
    }
  },
  
  // Multiplayer specific notifications
  multiplayer: (message, options = {}) => {
    if (window.showNotification) {
      return window.showNotification({
        type: 'multiplayer',
        message,
        duration: 2000,
        ...options
      });
    }
  },
  
  host: (message, options = {}) => {
    if (window.showNotification) {
      return window.showNotification({
        type: 'host',
        message,
        duration: 3000,
        important: true,
        ...options
      });
    }
  },
  
  action: (message, options = {}) => {
    if (window.showNotification) {
      return window.showNotification({
        type: 'action',
        message,
        duration: 2000,
        ...options
      });
    }
  },
  
  answer: (message, options = {}) => {
    if (window.showNotification) {
      return window.showNotification({
        type: 'answer',
        message,
        duration: 3000,
        important: true,
        ...options
      });
    }
  },
  
  waiting: (message, options = {}) => {
    if (window.showNotification) {
      return window.showNotification({
        type: 'waiting',
        message,
        duration: 2000,
        ...options
      });
    }
  }
};

export default NotificationSystem; 