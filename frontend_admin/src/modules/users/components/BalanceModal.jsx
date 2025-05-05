import React, { useState, useEffect } from 'react';
import Modal from '../../../shared/Modal';
import { useToast } from '../../../shared/ToastContext';
import './BalanceModal.css';

const API_BASE_URL = '/api';

const BalanceModal = ({ show, onClose, user, onRefresh }) => {
  const [balance, setBalance] = useState('0');
  const [amount, setAmount] = useState('');
  const [comment, setComment] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { showToast } = useToast();

  useEffect(() => {
    if (show && user) {
      setBalance(user.money?.toString() || '0');
      setAmount('');
      setComment('');
    }
  }, [show, user]);

  const handleUpdateBalance = async (action) => {
    if (!amount || isNaN(parseFloat(amount)) || parseFloat(amount) <= 0) {
      showToast('Введите корректную сумму', 'error');
      return;
    }

    setIsLoading(true);
    try {
      const endpoint = action === 'add' ? 'credit' : 'debit';
      const actionComment = comment.trim() || 
        (action === 'add' ? 'Ручное пополнение администратором' : 'Ручное списание администратором');

      const response = await fetch(`${API_BASE_URL}/transactions/${endpoint}`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json', 
          'Accept': 'application/json' 
        },
        credentials: 'include',
        body: JSON.stringify({
          user_id: user.id,
          amount: parseFloat(amount),
          comment: actionComment
        })
      });

      const result = await response.json();

      if (response.ok) {
        showToast(`Баланс успешно ${action === 'add' ? 'пополнен' : 'списан'} на ₸${amount}`, 'success');
        
        // Update local balance display
        try {
          const balResponse = await fetch(`${API_BASE_URL}/transactions/balance/${user.id}`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' },
            credentials: 'include'
          });
          
          const balData = await balResponse.json();
          
          if (balResponse.ok && balData.data?.balance !== undefined) {
            setBalance(balData.data.balance.toString());
          }
        } catch (error) {
          console.error('Error fetching updated balance:', error);
        }
        
        // Reset form
        setAmount('');
        setComment('');
        
        // Refresh user data in parent component
        if (onRefresh) {
          onRefresh();
        }
      } else {
        const errorMsg = result.details?.message || result.message || `Ошибка ${response.status}`;
        showToast(errorMsg, 'error');
      }
    } catch (error) {
      console.error('Error updating balance:', error);
      showToast('Ошибка соединения с сервером', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const footer = (
    <button className="btn-action" onClick={onClose} disabled={isLoading}>
      <i className='bx bx-x'></i>
      Закрыть
    </button>
  );

  return (
    <Modal 
      show={show} 
      onClose={onClose} 
      title="Управление балансом"
      footer={footer}
    >
      <div className="info-card">
        <h6 className="info-card-title">
          <i className='bx bx-user'></i> Информация о пользователе
        </h6>
        <div className="info-item">
          <span className="info-label">Пользователь:</span>
          <span className="info-value">{user?.full_name || 'Не указано'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Текущий баланс:</span>
          <span className="info-value info-highlight">₸ {balance}</span>
        </div>
      </div>

      <div className="info-card">
        <h6 className="info-card-title">
          <i className='bx bx-money'></i> Изменение баланса
        </h6>
        <form>
          <div className="form-group">
            <label htmlFor="balanceAmount" className="form-label">Сумма (₸)</label>
            <input 
              type="number" 
              className="form-control" 
              id="balanceAmount"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              min="1" 
              required
              disabled={isLoading}
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="balanceComment" className="form-label">Комментарий</label>
            <textarea 
              className="form-control" 
              id="balanceComment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              disabled={isLoading}
            />
          </div>
          
          <div className="balance-actions">
            <button 
              type="button" 
              className="balance-action-btn add"
              onClick={() => handleUpdateBalance('add')}
              disabled={isLoading}
            >
              <i className='bx bx-plus'></i>
              {isLoading ? 'Обработка...' : 'Пополнить'}
            </button>
            
            <button 
              type="button" 
              className="balance-action-btn remove"
              onClick={() => handleUpdateBalance('remove')}
              disabled={isLoading}
            >
              <i className='bx bx-minus'></i>
              {isLoading ? 'Обработка...' : 'Списать'}
            </button>
          </div>
        </form>
      </div>
    </Modal>
  );
};

export default BalanceModal; 