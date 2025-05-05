import React, { createContext, useState, useContext, useCallback } from 'react';

// Toast types
export const TOAST_TYPES = {
  SUCCESS: 'success',
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info',
};

// Create context
const ToastContext = createContext({
  showToast: () => {},
});

// Provider component
export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);

  // Generate a unique ID for each toast
  const generateId = () => `toast-${Date.now()}-${Math.floor(Math.random() * 1000)}`;

  // Show a toast notification
  const showToast = useCallback((message, type = TOAST_TYPES.INFO, duration = 5000) => {
    const id = generateId();
    
    // Add the new toast to the list
    setToasts(prevToasts => [...prevToasts, { id, message, type }]);
    
    // Remove the toast after the specified duration
    if (duration > 0) {
      setTimeout(() => {
        dismissToast(id);
      }, duration);
    }
    
    return id;
  }, []);

  // Dismiss a specific toast
  const dismissToast = useCallback((id) => {
    setToasts(prevToasts => prevToasts.filter(toast => toast.id !== id));
  }, []);

  // Toast display component
  const ToastContainer = () => {
    if (toasts.length === 0) return null;
    
    return (
      <div className="toast-container">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast toast-${toast.type}`}>
            <span className="toast-message">{toast.message}</span>
            <button className="toast-close" onClick={() => dismissToast(toast.id)}>×</button>
          </div>
        ))}
      </div>
    );
  };

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <ToastContainer />
    </ToastContext.Provider>
  );
};

// Hook for using the toast context
export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}; 