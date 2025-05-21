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
    
    // Check for duplicate toasts - don't add if the same message/type already exists
    const isDuplicate = toasts.some(toast => 
      toast.message === message && toast.type === type
    );
    
    if (isDuplicate) {
      return;
    }
    
    // Add the new toast to the list
    setToasts(prevToasts => [...prevToasts, { id, message, type }]);
    
    // Remove the toast after the specified duration
    if (duration > 0) {
      setTimeout(() => {
        dismissToast(id);
      }, duration);
    }
    
    return id;
  }, [toasts]);

  // Dismiss a specific toast
  const dismissToast = useCallback((id) => {
    setToasts(prevToasts => prevToasts.filter(toast => toast.id !== id));
  }, []);

  // Toast display component
  const ToastContainer = () => {
    if (toasts.length === 0) return null;
    
    return (
      <div className="toast-container" style={{ pointerEvents: 'none' }}>
        {toasts.map(toast => {
          // Set icon based on toast type
          let icon = 'bx-info-circle';
          if (toast.type === TOAST_TYPES.SUCCESS) icon = 'bx-check-circle';
          if (toast.type === TOAST_TYPES.ERROR) icon = 'bx-x-circle';
          if (toast.type === TOAST_TYPES.WARNING) icon = 'bx-error';
          
          return (
            <div key={toast.id} className={`toast ${toast.type}`} style={{ pointerEvents: 'auto' }}>
              <div className="toast-icon">
                <i className={`bx ${icon}`}></i>
              </div>
              <div className="toast-content">
                <span className="toast-message">{toast.message}</span>
              </div>
              <button className="toast-close" onClick={() => dismissToast(toast.id)}>×</button>
              <div className="toast-progress">
                <div className="toast-progress-inner"></div>
              </div>
            </div>
          );
        })}
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