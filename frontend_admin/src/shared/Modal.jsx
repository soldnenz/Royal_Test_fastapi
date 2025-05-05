import React, { useEffect } from 'react';
import './Modal.css';

const Modal = ({ 
  show, 
  onClose, 
  title, 
  children, 
  footer,
  size = 'medium' 
}) => {
  // Prevent background scrolling when modal is open
  useEffect(() => {
    if (show) {
      document.body.classList.add('modal-open');
    } else {
      document.body.classList.remove('modal-open');
    }
    
    return () => {
      document.body.classList.remove('modal-open');
    };
  }, [show]);

  if (!show) {
    return null;
  }

  // Close modal when clicking outside
  const handleBackdropClick = (e) => {
    if (e.target.classList.contains('modal')) {
      onClose();
    }
  };

  return (
    <div className="modal" onClick={handleBackdropClick}>
      <div className={`modal-content modal-${size}`}>
        <div className="modal-header">
          <h5 className="modal-title">{title}</h5>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          {children}
        </div>
        {footer && (
          <div className="modal-footer">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};

export default Modal; 