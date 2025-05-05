import React from 'react';
import './StatCard.css';

const StatCard = ({ title, value, icon, color = 'blue', percentChange, timeframe }) => {
  // Определение класса направления изменения (рост/падение)
  const changeClass = percentChange >= 0 ? 'increase' : 'decrease';
  
  // Определение иконки изменения
  const changeIcon = percentChange >= 0 ? 'bx bx-up-arrow-alt' : 'bx bx-down-arrow-alt';
  
  return (
    <div className={`stat-card stat-card-${color}`}>
      <div className="stat-card-icon">
        <i className={icon}></i>
      </div>
      <div className="stat-card-content">
        <h3 className="stat-card-title">{title}</h3>
        <div className="stat-card-value">{value}</div>
        {percentChange !== undefined && (
          <div className={`stat-card-change ${changeClass}`}>
            <i className={changeIcon}></i>
            <span>{Math.abs(percentChange)}%</span>
            <span className="timeframe">{timeframe}</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default StatCard; 