import React, { useState, useEffect } from 'react';
import Modal from '../../../shared/Modal';
import { useToast } from '../../../shared/ToastContext';
import './SubscriptionModal.css';

const API_BASE_URL = '/api';

const SubscriptionModal = ({ show, onClose, user, onRefresh }) => {
  const [formData, setFormData] = useState({
    subscription_type: 'economy',
    duration_days: 30,
    expires_at: '',
    activation_method: 'manual',
    note: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const { showToast } = useToast();

  useEffect(() => {
    if (show && user) {
      // Set default expiry date to 30 days from now
      const expiryDate = new Date();
      expiryDate.setDate(expiryDate.getDate() + 30);
      
      setFormData({
        subscription_type: 'economy',
        duration_days: 30,
        expires_at: expiryDate.toISOString().split('T')[0],
        activation_method: 'manual',
        note: ''
      });
    }
  }, [show, user]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    
    if (name === 'duration_days') {
      // Update expires_at when duration_days changes
      const days = parseInt(value);
      if (!isNaN(days)) {
        const expiryDate = new Date();
        expiryDate.setDate(expiryDate.getDate() + days);
        
        setFormData(prev => ({
          ...prev,
          [name]: value,
          expires_at: expiryDate.toISOString().split('T')[0]
        }));
      } else {
        setFormData(prev => ({ ...prev, [name]: value }));
      }
    } else if (name === 'expires_at') {
      // Update duration_days when expires_at changes
      const selectedDate = new Date(value);
      const now = new Date();
      const diffTime = selectedDate - now;
      const days = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      
      setFormData(prev => ({
        ...prev,
        [name]: value,
        duration_days: days > 0 ? days : 0
      }));
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.subscription_type || !formData.expires_at || formData.duration_days <= 0) {
      showToast('Пожалуйста, заполните все обязательные поля', 'error');
      return;
    }

    setIsLoading(true);
    try {
      const payload = {
        user_id: user.id,
        iin: user.iin,
        subscription_type: formData.subscription_type.toLowerCase(),
        expires_at: new Date(formData.expires_at).toISOString(),
        activation_method: formData.activation_method,
        note: formData.note || "",
        duration_days: parseInt(formData.duration_days)
      };
      
      const response = await fetch(`${API_BASE_URL}/subscriptions/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail?.message || `Ошибка ${response.status}`);
      }
      
      await response.json();
      
      showToast('✅ Подписка успешно выдана!', 'success');
      onClose();
      
      // Refresh user data
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      console.error('Error creating subscription:', error);
      showToast(`Ошибка при создании подписки: ${error.message}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const footer = (
    <>
      <button className="btn-action" onClick={onClose} disabled={isLoading}>
        <i className='bx bx-x'></i>
        Отмена
      </button>
      <button 
        className="btn-action btn-primary" 
        onClick={handleSubmit}
        disabled={isLoading}
      >
        <i className='bx bx-check'></i>
        {isLoading ? 'Создание...' : 'Подтвердить'}
      </button>
    </>
  );

  return (
    <Modal 
      show={show} 
      onClose={onClose} 
      title="Выдать подписку"
      footer={footer}
    >
      <div className="info-card">
        <h6 className="info-card-title">
          <i className='bx bx-user'></i> Информация о пользователе
        </h6>
        <div className="info-item">
          <span className="info-label">Имя:</span>
          <span className="info-value">{user?.full_name || '-'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">ИИН:</span>
          <span className="info-value">{user?.iin || '-'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Email:</span>
          <span className="info-value">{user?.email || '-'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Телефон:</span>
          <span className="info-value">{user?.phone || '-'}</span>
        </div>
      </div>

      <div className="info-card">
        <h6 className="info-card-title">
          <i className='bx bx-crown'></i> Параметры подписки
        </h6>
        <form>
          <div className="form-group">
            <label htmlFor="subscription_type" className="form-label">Тип подписки</label>
            <select
              className="form-control"
              id="subscription_type"
              name="subscription_type"
              value={formData.subscription_type}
              onChange={handleInputChange}
              required
              disabled={isLoading}
            >
              <option value="demo">Demo</option>
              <option value="economy">Economy</option>
              <option value="vip">VIP</option>
              <option value="royal">Royal</option>
              <option value="school">School</option>
            </select>
          </div>
          
          <div className="form-group">
            <label htmlFor="duration_days" className="form-label">Срок действия (дней)</label>
            <input
              type="number"
              className="form-control"
              id="duration_days"
              name="duration_days"
              value={formData.duration_days}
              onChange={handleInputChange}
              min="1"
              required
              disabled={isLoading}
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="expires_at" className="form-label">Действует до</label>
            <input
              type="date"
              className="form-control"
              id="expires_at"
              name="expires_at"
              value={formData.expires_at}
              onChange={handleInputChange}
              required
              disabled={isLoading}
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="activation_method" className="form-label">Способ активации</label>
            <select
              className="form-control"
              id="activation_method"
              name="activation_method"
              value={formData.activation_method}
              onChange={handleInputChange}
              required
              disabled={isLoading}
            >
              <option value="manual">Вручную</option>
            </select>
          </div>
          
          <div className="form-group">
            <label htmlFor="note" className="form-label">Комментарий</label>
            <textarea
              className="form-control"
              id="note"
              name="note"
              value={formData.note}
              onChange={handleInputChange}
              disabled={isLoading}
            />
          </div>
        </form>
      </div>
    </Modal>
  );
};

export default SubscriptionModal; 