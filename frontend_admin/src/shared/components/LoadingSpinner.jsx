import React from 'react';
import './SharedComponents.css';

const LoadingSpinner = ({ size = 'medium', message = 'Загрузка...' }) => {
  const spinnerSizeClass = {
    small: 'spinner-small',
    medium: 'spinner-medium',
    large: 'spinner-large'
  }[size] || 'spinner-medium';

  return (
    <div className="loading-container">
      <div className={`spinner ${spinnerSizeClass}`}></div>
      {message && <p className="loading-message">{message}</p>}
    </div>
  );
};

export default LoadingSpinner; 