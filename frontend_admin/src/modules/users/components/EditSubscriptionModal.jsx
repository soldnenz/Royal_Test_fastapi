import React, { useState, useEffect } from 'react';
import Modal from '../../../shared/Modal';
import { useToast } from '../../../shared/ToastContext';
import './EditSubscriptionModal.css';

const API_BASE_URL = '/api';

const EditSubscriptionModal = ({ show, onClose, user, onRefresh }) => {
  const [subscriptionData, setSubscriptionData] = useState(null);
  const [formData, setFormData] = useState({
    subscription_type: '',
    duration_days: 0,
    expires_at: '',
    note: ''
  });
  const [cancelReason, setCancelReason] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const { showToast } = useToast();

  useEffect(() => {
    if (show && user) {
      fetchSubscriptionData();
    }
  }, [show, user]);

  const fetchSubscriptionData = async () => {
    setIsLoadingData(true);
    try {
      const response = await fetch(`${API_BASE_URL}/subscriptions/user/${user.id}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include'
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail?.message || 'Ошибка получения данных подписки');
      }
      
      const data = await response.json();
      
      if ((data.status !== 'success' && data.status !== 'ok') || !data.data) {
        throw new Error('Ошибка получения данных подписки');
      }
      
      const subscription = data.data;
      setSubscriptionData(subscription);
      
      // Calculate remaining days
      const expiresDate = new Date(subscription.expires_at);
      
      // Validate the date from server
      if (isNaN(expiresDate.getTime())) {
        console.error('Invalid expiry date from server:', subscription.expires_at);
        showToast('Некорректная дата подписки получена с сервера', 'error');
        onClose();
        return;
      }
      
      const now = new Date();
      const remainingDays = Math.ceil((expiresDate - now) / (1000 * 60 * 60 * 24));
      
      setFormData({
        subscription_type: subscription.subscription_type.toLowerCase(),
        duration_days: remainingDays > 0 ? remainingDays : 0,
        expires_at: expiresDate.toISOString().split('T')[0],
        note: ''
      });
    } catch (error) {
      console.error('Error fetching subscription details:', error);
      showToast('Ошибка при загрузке данных подписки', 'error');
      onClose();
    } finally {
      setIsLoadingData(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    
    if (name === 'duration_days') {
      // Update expires_at when duration_days changes
      const days = parseInt(value);
      
      // Validate the input
      if (!isNaN(days) && days >= 0 && days <= 3650) { // Max 10 years
        try {
          const expiryDate = new Date();
          expiryDate.setDate(expiryDate.getDate() + days);
          
          // Verify the date is valid
          if (isNaN(expiryDate.getTime())) {
            console.error('Invalid date calculated for days:', days);
            setFormData(prev => ({ ...prev, [name]: value }));
            return;
          }
          
          setFormData(prev => ({
            ...prev,
            [name]: value,
            expires_at: expiryDate.toISOString().split('T')[0]
          }));
        } catch (error) {
          console.error('Error calculating expiry date:', error);
          setFormData(prev => ({ ...prev, [name]: value }));
        }
      } else {
        // Just update the days field without calculating expires_at for invalid values
        setFormData(prev => ({ ...prev, [name]: value }));
      }
    } else if (name === 'expires_at') {
      // Update duration_days when expires_at changes
      try {
        const selectedDate = new Date(value);
        
        // Verify the selected date is valid
        if (isNaN(selectedDate.getTime())) {
          console.error('Invalid date selected:', value);
          setFormData(prev => ({ ...prev, [name]: value }));
          return;
        }
        
        const now = new Date();
        const diffTime = selectedDate - now;
        const days = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        setFormData(prev => ({
          ...prev,
          [name]: value,
          duration_days: days > 0 ? days : 0
        }));
      } catch (error) {
        console.error('Error parsing date:', error);
        setFormData(prev => ({ ...prev, [name]: value }));
      }
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleUpdateSubscription = async () => {
    if (!formData.subscription_type || !formData.expires_at || formData.duration_days <= 0) {
      showToast('Пожалуйста, заполните все обязательные поля', 'error');
      return;
    }

    // Validate date before sending
    const expiryDate = new Date(formData.expires_at);
    if (isNaN(expiryDate.getTime())) {
      showToast('Некорректная дата окончания подписки', 'error');
      return;
    }

    setIsLoading(true);
    try {
      const payload = {
        subscription_id: subscriptionData._id || subscriptionData.id,
        subscription_type: formData.subscription_type.toLowerCase(),
        expires_at: expiryDate.toISOString(),
        duration_days: parseInt(formData.duration_days),
        note: formData.note || 'Изменение администратором'
      };
      
      const response = await fetch(`${API_BASE_URL}/subscriptions/update`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
      
      const result = await response.json();
      
      if (response.ok) {
        showToast('✅ Подписка успешно обновлена!', 'success');
        onClose();
        
        // Refresh user data
        if (onRefresh) {
          onRefresh();
        }
      } else {
        const errMsg = result.detail?.message || result.message || `Ошибка ${response.status}`;
        showToast(errMsg, 'error');
      }
    } catch (error) {
      console.error('Error updating subscription:', error);
      showToast('Ошибка при обновлении подписки', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancelSubscription = async () => {
    if (!cancelReason.trim()) {
      showToast('Укажите причину отмены подписки', 'error');
      return;
    }
    
    if (!confirm('Вы уверены, что хотите отменить подписку?')) {
      return;
    }
    
    setIsLoading(true);
    try {
      const payload = {
        subscription_id: subscriptionData._id || subscriptionData.id,
        cancel_reason: cancelReason
      };
      
      const response = await fetch(`${API_BASE_URL}/subscriptions/cancel`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
      
      const result = await response.json();
      
      if (response.ok) {
        showToast('✅ Подписка успешно отменена!', 'success');
        onClose();
        
        // Refresh user data
        if (onRefresh) {
          onRefresh();
        }
      } else {
        const errMsg = result.detail?.message || result.message || `Ошибка ${response.status}`;
        showToast(errMsg, 'error');
      }
    } catch (error) {
      console.error('Error canceling subscription:', error);
      showToast('Ошибка при отмене подписки', 'error');
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
        onClick={handleUpdateSubscription}
        disabled={isLoading || isLoadingData}
      >
        <i className='bx bx-check'></i>
        {isLoading ? 'Сохранение...' : 'Сохранить изменения'}
      </button>
    </>
  );

  if (isLoadingData) {
    return (
      <Modal 
        show={show} 
        onClose={onClose} 
        title="Редактирование подписки"
        footer={footer}
      >
        <div className="loading-container">Загрузка данных подписки...</div>
      </Modal>
    );
  }

  return (
    <Modal 
      show={show} 
      onClose={onClose} 
      title="Редактирование подписки"
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
          <span className="info-label">ID пользователя:</span>
          <span className="info-value">{user?.id || '-'}</span>
        </div>
      </div>

      <div className="info-card">
        <h6 className="info-card-title">
          <i className='bx bx-crown'></i> Текущая подписка
        </h6>
        {subscriptionData && (
          <>
            <div className="info-item">
              <span className="info-label">Текущий тип:</span>
              <span className="info-value">{subscriptionData.subscription_type || '-'}</span>
            </div>
            <div className="info-item">
              <span className="info-label">Осталось дней:</span>
              <span className="info-value">{formData.duration_days}</span>
            </div>
            <div className="info-item">
              <span className="info-label">Действует до:</span>
              <span className="info-value">
                {subscriptionData.expires_at 
                  ? (() => {
                      try {
                        const date = new Date(subscriptionData.expires_at);
                        return isNaN(date.getTime()) ? 'Некорректная дата' : date.toLocaleDateString();
                      } catch (error) {
                        return 'Ошибка даты';
                      }
                    })()
                  : '-'}
              </span>
            </div>
          </>
        )}
      </div>

      <div className="info-card">
        <h6 className="info-card-title">
          <i className='bx bx-edit'></i> Изменить параметры подписки
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
            <label htmlFor="duration_days" className="form-label">Оставшиеся дни</label>
            <input
              type="number"
              className="form-control"
              id="duration_days"
              name="duration_days"
              value={formData.duration_days}
              onChange={handleInputChange}
              min="0"
              max="3650"
              step="1"
              required
              disabled={isLoading}
              title="Введите количество дней от 0 до 3650 (максимум 10 лет)"
            />
            <small className="form-text">Максимум 3650 дней (≈10 лет)</small>
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
            <label htmlFor="note" className="form-label">Комментарий к изменениям</label>
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

      <div className="info-card cancel-subscription-card">
        <h6 className="info-card-title danger-title">
          <i className='bx bx-x-circle'></i> Отменить подписку
        </h6>
        <div className="form-group">
          <label htmlFor="cancelReason" className="form-label">Причина отмены</label>
          <textarea
            className="form-control"
            id="cancelReason"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            disabled={isLoading}
          />
        </div>
        <button 
          type="button" 
          className="btn-action btn-danger" 
          onClick={handleCancelSubscription}
          disabled={isLoading}
        >
          <i className='bx bx-x'></i>
          {isLoading ? 'Отмена подписки...' : 'Отменить подписку'}
        </button>
      </div>
    </Modal>
  );
};

export default EditSubscriptionModal; 