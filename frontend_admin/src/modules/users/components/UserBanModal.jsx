import React, { useState, useEffect } from 'react';
import Modal from '../../../shared/Modal';
import { useToast } from '../../../shared/ToastContext';
import './UserBanModal.css';

const API_BASE_URL = '/api';

const UserBanModal = ({ show, onClose, user, onRefresh }) => {
  const [banData, setBanData] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const [banFormData, setBanFormData] = useState({
    duration_type: 'temporary',
    days: 1,
    reason: ''
  });
  const [unbanReason, setUnbanReason] = useState('');
  const [isUserBanned, setIsUserBanned] = useState(user?.is_banned || false);
  const { showToast } = useToast();

  // Just fetch ban data when modal shows
  useEffect(() => {
    if (show && user) {
      fetchBanData();
    }
  }, [show, user]);

  const fetchBanData = async () => {
    if (!user || !user.id) return;
    
    setIsLoadingData(true);
    try {
      const response = await fetch(`${API_BASE_URL}/admin_function/bans/${user.id}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        
        if ((data.status === 'success' || data.status === 'ok') && Array.isArray(data.data)) {
          setBanData(data.data);
          
          // Check if there's an active ban
          const hasActiveBan = data.data.some(ban => ban.is_active);
          setIsUserBanned(hasActiveBan);
          
          // Update user ban status if needed (without additional API calls)
          if (hasActiveBan !== user.is_banned) {
            onRefresh && onRefresh({ ...user, is_banned: hasActiveBan });
          }
        } else {
          setBanData([]);
          
          // If no ban data but user is marked as banned, update status
          if (user.is_banned) {
            setIsUserBanned(false);
            onRefresh && onRefresh({ ...user, is_banned: false });
          }
        }
      } else {
        setBanData([]);
      }
    } catch (error) {
      console.error('Error fetching ban data:', error);
      setBanData([]);
    } finally {
      setIsLoadingData(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setBanFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleBanUser = async () => {
    if (!banFormData.reason.trim()) {
      showToast('Укажите причину блокировки', 'error');
      return;
    }
    
    if (banFormData.duration_type === 'temporary' && (!banFormData.days || banFormData.days < 1)) {
      showToast('Укажите корректный срок блокировки', 'error');
      return;
    }
    
    setIsLoading(true);
    try {
      const payload = {
        user_id: user.id,
        ban_type: banFormData.duration_type,
        ban_days: banFormData.duration_type === 'temporary' ? parseInt(banFormData.days) : null,
        reason: banFormData.reason
      };
      
      const response = await fetch(`${API_BASE_URL}/admin_function/ban`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
      
      const result = await response.json();
      
      if (response.ok) {
        setIsUserBanned(true);
        onRefresh && onRefresh({ ...user, is_banned: true });
        showToast('Пользователь успешно заблокирован', 'success');
        onClose();
      } else {
        const errMsg = result.detail?.message || result.message || `Ошибка ${response.status}`;
        showToast(errMsg, 'error');
      }
    } catch (error) {
      console.error('Error banning user:', error);
      showToast('Ошибка при блокировке пользователя', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUnbanUser = async () => {
    if (!unbanReason.trim()) {
      showToast('Укажите причину разблокировки', 'error');
      return;
    }
    
    if (!confirm('Вы уверены, что хотите разблокировать пользователя?')) {
      return;
    }
    
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/admin_function/unban/${user.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ reason: unbanReason })
      });
      
      const result = await response.json();
      
      if (response.ok) {
        setIsUserBanned(false);
        onRefresh && onRefresh({ ...user, is_banned: false });
        showToast('Пользователь успешно разблокирован', 'success');
        onClose();
      } else {
        const errMsg = result.detail?.message || result.message || `Ошибка ${response.status}`;
        showToast(errMsg, 'error');
      }
    } catch (error) {
      console.error('Error unbanning user:', error);
      showToast('Ошибка при разблокировке пользователя', 'error');
    } finally {
      setIsLoading(false);
    }
  };
  
  const toggleBanDuration = () => {
    const banDaysGroup = document.getElementById('ban_days_group');
    if (banDaysGroup) {
      banDaysGroup.style.display = banFormData.duration_type === 'permanent' ? 'none' : 'block';
    }
  };

  useEffect(() => {
    if (show) {
      toggleBanDuration();
    }
  }, [banFormData.duration_type, show]);

  const activeBan = banData.find(ban => ban?.is_active);
  const hasBanHistory = banData.length > 0;

  const footer = (
    <button className="btn-action" onClick={onClose} disabled={isLoading}>
      <i className='bx bx-x'></i>
      Закрыть
    </button>
  );

  if (isLoadingData) {
    return (
      <Modal 
        show={show} 
        onClose={onClose} 
        title="Управление блокировкой"
        footer={footer}
      >
        <div className="loading-container">Загрузка данных...</div>
      </Modal>
    );
  }

  return (
    <Modal 
      show={show} 
      onClose={onClose} 
      title="Управление блокировкой"
      footer={footer}
    >
      <div className="info-card">
        <h6 className="info-card-title">
          <i className='bx bx-user'></i> Информация о пользователе
        </h6>
        <div className="info-item">
          <span className="info-label">Имя:</span>
          <span className="info-value">{user?.full_name || 'Не указано'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">ID пользователя:</span>
          <span className="info-value">{user?.id}</span>
        </div>
        <div className={`info-item ${isUserBanned ? 'banned-status' : 'active-status'}`}>
          <span className="info-label">СТАТУС:</span>
          <span className="info-value">
            {isUserBanned ? 'ЗАБЛОКИРОВАН' : 'АКТИВЕН'}
          </span>
        </div>
      </div>

      {isUserBanned ? (
        <div className="info-card active-ban-card">
          <h6 className="info-card-title ban-title">
            <i className='bx bx-block'></i> Активная блокировка
          </h6>
          
          {activeBan && (
            <>
              <div className="info-item ban-type">
                <span className="info-label">Тип блокировки:</span>
                <span className="info-value">
                  {activeBan.ban_type === 'permanent' ? 'Бессрочная' : 'Временная'}
                </span>
              </div>
              
              <div className="info-item ban-detail">
                <span className="info-label">Причина блокировки:</span>
                <span className="info-value">{activeBan.reason || 'Не указана'}</span>
              </div>
              
              <div className="info-item ban-detail">
                <span className="info-label">Дата блокировки:</span>
                <span className="info-value">
                  {activeBan.created_at ? new Date(activeBan.created_at).toLocaleString() : '-'}
                </span>
              </div>
              
              <div className="info-item ban-detail">
                <span className="info-label">Кем заблокирован:</span>
                <span className="info-value">{activeBan.admin_name || 'Не указан'}</span>
              </div>
              
              {activeBan.ban_type === 'temporary' && activeBan.ban_until && (
                <>
                  <div className="info-item ban-detail">
                    <span className="info-label">Дата разблокировки:</span>
                    <span className="info-value">
                      {new Date(activeBan.ban_until).toLocaleString()}
                    </span>
                  </div>
                  
                  {new Date(activeBan.ban_until) > new Date() ? (
                    <div className="info-item ban-detail">
                      <span className="info-label">Осталось до разблокировки:</span>
                      <span className="info-value">
                        {Math.ceil((new Date(activeBan.ban_until) - new Date()) / (1000 * 60 * 60 * 24))} дн.
                      </span>
                    </div>
                  ) : (
                    <div className="info-item ban-detail">
                      <span className="info-label">Статус блокировки:</span>
                      <span className="info-value">
                        Срок истек, но пользователь не разблокирован
                      </span>
                    </div>
                  )}
                </>
              )}
            </>
          )}
          
          <div className="form-group mt-3">
            <label htmlFor="unban_reason" className="form-label">
              Причина разблокировки
            </label>
            <textarea 
              className="form-control" 
              id="unban_reason" 
              placeholder="Укажите причину разблокировки" 
              value={unbanReason}
              onChange={(e) => setUnbanReason(e.target.value)}
              required
              disabled={isLoading}
            />
            <small className="form-text text-muted">
              Причина разблокировки будет сохранена в истории блокировок пользователя.
            </small>
          </div>
          
          <div className="text-center mt-3">
            <button 
              className="btn-action btn-success" 
              id="unbanConfirmButton"
              onClick={handleUnbanUser}
              disabled={isLoading}
            >
              <i className='bx bx-check-shield'></i>
              {isLoading ? 'Разблокировка...' : 'Разблокировать пользователя'}
            </button>
          </div>
        </div>
      ) : (
        <div className="info-card" id="banFormCard">
          <h6 className="info-card-title">
            <i className='bx bx-shield-x'></i> Создать блокировку
          </h6>
          <form id="banUserForm">
            <div className="form-group">
              <label htmlFor="duration_type" className="form-label">Тип блокировки</label>
              <select 
                className="form-control" 
                id="duration_type" 
                name="duration_type"
                value={banFormData.duration_type}
                onChange={handleInputChange}
                disabled={isLoading}
              >
                <option value="temporary">Временная</option>
                <option value="permanent">Бессрочная</option>
              </select>
              <small className="form-text text-muted" id="ban_type_help">
                Временная блокировка будет автоматически снята по истечении срока.
              </small>
            </div>
            
            <div className="form-group" id="ban_days_group">
              <label htmlFor="days" className="form-label">Срок блокировки (дней)</label>
              <input 
                type="number" 
                className="form-control" 
                id="days" 
                name="days"
                min="1" 
                value={banFormData.days}
                onChange={handleInputChange}
                disabled={isLoading || banFormData.duration_type === 'permanent'}
              />
              <small className="form-text text-muted">
                Укажите количество дней, на которое нужно заблокировать пользователя.
              </small>
            </div>
            
            <div className="form-group">
              <label htmlFor="reason" className="form-label">Причина блокировки</label>
              <textarea 
                className="form-control" 
                id="reason" 
                name="reason"
                value={banFormData.reason}
                onChange={handleInputChange}
                placeholder="Укажите причину блокировки"
                required
                disabled={isLoading}
              />
              <small className="form-text text-muted">
                Причина блокировки будет видна в истории блокировок и пользователю.
              </small>
            </div>
            
            <div className="text-center">
              <button 
                type="button" 
                className="btn-action btn-danger" 
                id="banButton"
                onClick={handleBanUser}
                disabled={isLoading}
              >
                <i className='bx bx-shield-x'></i>
                {isLoading ? 'Блокировка...' : 'Заблокировать пользователя'}
              </button>
            </div>
          </form>
        </div>
      )}

      {hasBanHistory && (
        <div className="info-card" id="banHistoryCard">
          <h6 className="info-card-title">
            <i className='bx bx-history'></i> История блокировок
          </h6>
          <table className="history-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Тип</th>
                <th>Причина</th>
                <th>Администратор</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {banData.sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).map((ban, index) => (
                <tr key={index} className={ban.is_active ? 'active-ban' : ''}>
                  <td>{new Date(ban.created_at).toLocaleDateString()}</td>
                  <td>
                    {ban.ban_type === 'permanent' ? 'Бессрочная' : 'Временная'}
                    {ban.ban_type === 'temporary' && ban.ban_until && (
                      <div className="ban-duration">
                        Срок: {Math.ceil((new Date(ban.ban_until) - new Date(ban.created_at)) / (1000 * 60 * 60 * 24))} дн.
                      </div>
                    )}
                  </td>
                  <td>{ban.reason || 'Не указана'}</td>
                  <td>{ban.admin_name || 'Не указан'}</td>
                  <td>
                    {ban.is_active ? (
                      <span className="badge badge-danger">Активна</span>
                    ) : ban.unbanned_by ? (
                      <div>
                        <span className="badge badge-secondary">Снята</span>
                        <div className="unban-info">
                          {ban.unbanned_by.admin_name || 'Админ'}
                          <br />
                          {new Date(ban.unbanned_by.timestamp).toLocaleDateString()}
                          <br />
                          <span className="unban-reason">
                            "{ban.unbanned_by.reason || 'Не указана'}"
                          </span>
                        </div>
                      </div>
                    ) : (
                      <span className="badge badge-secondary">Истекла</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
};

export default UserBanModal; 