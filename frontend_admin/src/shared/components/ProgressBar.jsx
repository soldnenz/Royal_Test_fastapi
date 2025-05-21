import React from 'react';

/**
 * ProgressBar component for showing progress of operations like uploads
 * @param {Object} props - Component props
 * @param {number} props.progress - Progress percentage (0-100)
 * @param {string} props.label - Optional label to show
 * @param {string} props.color - Optional color for the progress bar
 */
const ProgressBar = ({ progress, label, color = '#4caf50' }) => {
  // Ensure progress is between 0 and 100
  const safeProgress = Math.min(Math.max(progress, 0), 100);
  
  return (
    <div className="progress-container" style={{ 
      width: '100%', 
      backgroundColor: '#e0e0e0',
      borderRadius: '4px',
      margin: '10px 0',
      overflow: 'hidden',
      position: 'relative'
    }}>
      <div className="progress-inner" style={{
        width: `${safeProgress}%`,
        backgroundColor: color,
        height: '20px',
        transition: 'width 0.3s ease'
      }}></div>
      
      {label && (
        <div className="progress-label" style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: safeProgress > 50 ? 'white' : '#333',
          fontSize: '12px',
          fontWeight: 'bold'
        }}>
          {label}
        </div>
      )}
      
      {!label && safeProgress > 0 && (
        <div className="progress-percentage" style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: safeProgress > 50 ? 'white' : '#333',
          fontSize: '12px',
          fontWeight: 'bold'
        }}>
          {Math.round(safeProgress)}%
        </div>
      )}
    </div>
  );
};

export default ProgressBar; 