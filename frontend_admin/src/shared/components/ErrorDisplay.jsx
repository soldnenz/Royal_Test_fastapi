import React from 'react';
import './SharedComponents.css';

const ErrorDisplay = ({ message, onRetry }) => {
  return (
    <div className="error-container">
      <div className="error-icon">⚠️</div>
      <h3 className="error-title">Произошла ошибка</h3>
      <p className="error-message">{message}</p>
      {onRetry && (
        <button className="error-retry-button" onClick={onRetry}>
          Попробовать снова
        </button>
      )}
    </div>
  );
};

export default ErrorDisplay; 