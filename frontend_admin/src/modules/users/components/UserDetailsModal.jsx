import React, { useState, useEffect } from 'react';
import Modal from '../../../shared/Modal';
import { useToast } from '../../../shared/ToastContext';
import './UserDetailsModal.css';

const API_BASE_URL = '/api';

const UserDetailsModal = ({ show, onClose, userId, onRefresh }) => {
  const [userData, setUserData] = useState(null);
  const [banData, setBanData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [unbanReason, setUnbanReason] = useState('');
  const { showToast } = useToast();

  useEffect(() => {
    if (show && userId) {
      fetchUserDetails();
    }
  }, [show, userId]);

  const fetchUserDetails = async () => {
    setIsLoading(true);
    try {
      // Fetch user details
      const response = await fetch(`${API_BASE_URL}/users/admin/search_users?query=${userId}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error('Failed to fetch user details');
      }
      
      const data = await response.json();
      
      if ((data.status !== 'success' && data.status !== 'ok') || !data.data || !data.data.length) {
        throw new Error('User details not found');
      }
      
      const user = data.data[0];
      setUserData(user);
      
      // If user is banned, fetch ban details
      if (user.is_banned) {
        try {
          const banResponse = await fetch(`${API_BASE_URL}/admin_function/bans/${userId}`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
          });
          
          if (banResponse.ok) {
            const banData = await banResponse.json();
            if (banData.status === 'success' && banData.data && banData.data.length > 0) {
              setBanData(banData.data);
            }
          }
        } catch (error) {
          console.error('Error fetching ban details:', error);
        }
      }
    } catch (error) {
      console.error('Error fetching user details:', error);
      showToast('Ошибка при загрузке данных пользователя', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUnban = async () => {
    if (!unbanReason.trim()) {
      showToast('Укажите причину разблокировки', 'error');
      return;
    }
    
    if (!confirm('Вы уверены, что хотите разблокировать пользователя?')) {
      return;
    }
    
    try {
      showToast('Разблокировка пользователя...', 'info');
      
      const response = await fetch(`${API_BASE_URL}/admin_function/unban/${userId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ reason: unbanReason })
      });
      
      const result = await response.json();
      
      if (response.ok) {
        showToast('Пользователь успешно разблокирован', 'success');
        onClose();
        if (onRefresh) onRefresh();
      } else {
        const errMsg = result.detail?.message || result.message || `Ошибка ${response.status}`;
        showToast(errMsg, 'error');
      }
    } catch (error) {
      console.error('Error unbanning user:', error);
      showToast('Ошибка при разблокировке пользователя', 'error');
    }
  };

  const renderMainInfo = () => {
    if (!userData) return <div className="loading-text">Загрузка информации...</div>;
    
    return (
      <>
        <div className="info-item">
          <span className="info-label">ID пользователя:</span>
          <span className="info-value">{userData.id || '-'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">ИИН:</span>
          <span className="info-value">{userData.iin || '-'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Имя:</span>
          <span className="info-value">{userData.full_name || '-'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Email:</span>
          <span className="info-value">{userData.email || '-'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Телефон:</span>
          <span className="info-value">{userData.phone || '-'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Баланс:</span>
          <span className="info-value info-highlight">₸ {userData.money || '0'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Дата регистрации:</span>
          <span className="info-value">{userData.created_at ? new Date(userData.created_at).toLocaleString() : '-'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Приглашен по коду:</span>
          <span className="info-value">{userData.referred_by || 'Нет'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Использовал реферальную систему:</span>
          <span className="info-value">{userData.referred_use ? 'Да' : 'Нет'}</span>
        </div>
      </>
    );
  };

  const renderBlockingInfo = () => {
    if (!userData) return <div className="loading-text">Загрузка информации о блокировке...</div>;

    if (userData.is_banned) {
      const activeBan = banData?.find(ban => ban.is_active) || banData?.[0];
      
      return (
        <>
          <div className="info-item banned-status">
            <span className="info-label">СТАТУС:</span>
            <span className="info-value">ПОЛЬЗОВАТЕЛЬ ЗАБЛОКИРОВАН</span>
          </div>
          
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
                <span className="info-label">Кем заблокирован:</span>
                <span className="info-value">{activeBan.admin_name || 'Не указан'}</span>
              </div>
              
              <div className="info-item ban-detail">
                <span className="info-label">Дата блокировки:</span>
                <span className="info-value">
                  {activeBan.created_at ? new Date(activeBan.created_at).toLocaleString() : '-'}
                </span>
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
            <label htmlFor="unban_reason_details" className="form-label">
              Причина разблокировки
            </label>
            <textarea 
              className="form-control" 
              id="unban_reason_details" 
              placeholder="Укажите причину разблокировки" 
              value={unbanReason}
              onChange={(e) => setUnbanReason(e.target.value)}
              required
            />
            <small className="form-text text-muted">
              Причина разблокировки будет сохранена в истории блокировок.
            </small>
          </div>
          
          <div className="text-center mt-3">
            <button 
              className="btn-action btn-success" 
              onClick={handleUnban}
            >
              <i className='bx bx-check-shield'></i>
              Разблокировать пользователя
            </button>
          </div>
          
          {banData && banData.length > 1 && (
            <div className="ban-history">
              <h6 className="ban-history-title">
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
        </>
      );
    }

    return (
      <>
        <div className="info-item active-status">
          <span className="info-label">СТАТУС:</span>
          <span className="info-value">АКТИВЕН</span>
        </div>
      </>
    );
  };

  const renderSubscriptionInfo = () => {
    if (!userData) return <div className="loading-text">Загрузка информации о подписке...</div>;

    if (userData.subscription) {
      const subscriptionActive = userData.subscription.is_active;
      
      return (
        <>
          <div className="info-item">
            <span className="info-label">Тип подписки:</span>
            <span className="info-value">
              <span className={`badge ${subscriptionActive ? 'badge-success' : 'badge-secondary'}`}>
                <i className={`bx ${subscriptionActive ? 'bx-check-circle' : 'bx-x-circle'}`}></i>
                {userData.subscription.subscription_type || '-'}
              </span>
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">Статус:</span>
            <span className="info-value">
              {subscriptionActive ? 'Активна' : 'Неактивна'}
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">Действует до:</span>
            <span className="info-value">
              {userData.subscription.expires_at ? new Date(userData.subscription.expires_at).toLocaleString() : '-'}
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">Способ активации:</span>
            <span className="info-value">
              {userData.subscription.activation_method || '-'}
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">Дата выдачи:</span>
            <span className="info-value">
              {userData.subscription.created_at ? new Date(userData.subscription.created_at).toLocaleString() : '-'}
            </span>
          </div>
        </>
      );
    }

    return (
      <div className="info-item">
        <span className="info-label">Статус:</span>
        <span className="info-value">Нет активной подписки</span>
      </div>
    );
  };

  const renderSubscriptionHistory = () => {
    if (!userData) return <div className="loading-text">Загрузка истории подписок...</div>;

    if (userData.subscription_history && userData.subscription_history.length > 0) {
      return (
        <table className="history-table">
          <thead>
            <tr>
              <th>Дата</th>
              <th>Тип</th>
              <th>Срок</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            {userData.subscription_history.map((sub, index) => (
              <tr key={index}>
                <td>{sub.date ? new Date(sub.date).toLocaleDateString() : '-'}</td>
                <td>{sub.type || '-'}</td>
                <td>{sub.duration || '-'}</td>
                <td>
                  <span className={`badge ${sub.status === 'Активна' ? 'badge-success' : 'badge-secondary'}`}>
                    {sub.status || '-'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      );
    }

    return <div className="text-center">История подписок отсутствует</div>;
  };

  const renderReferralInfo = () => {
    if (!userData) return <div className="loading-text">Загрузка реферальной информации...</div>;

    if (userData.referral_system) {
      return (
        <>
          <div className="info-item">
            <span className="info-label">Реферальный код:</span>
            <span className="info-value info-highlight">
              {userData.referral_system.code || '-'}
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">Привел пользователей:</span>
            <span className="info-value">
              {userData.referral_system.referred_users_count || '0'}
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">Заработано бонусов:</span>
            <span className="info-value">
              ₸ {userData.referral_system.earned_bonus || '0'}
            </span>
          </div>
        </>
      );
    }

    return <div className="text-center">Реферальная информация отсутствует</div>;
  };

  const renderActivityInfo = () => {
    if (!userData) return <div className="loading-text">Загрузка информации о активности...</div>;

    if (userData.last_activity) {
      return (
        <>
          <div className="info-item">
            <span className="info-label">Последний вход:</span>
            <span className="info-value">
              {userData.last_activity.last_login ? new Date(userData.last_activity.last_login).toLocaleString() : '-'}
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">IP адрес:</span>
            <span className="info-value">{userData.last_activity.ip_address || '-'}</span>
          </div>
          <div className="info-item">
            <span className="info-label">Устройство:</span>
            <span className="info-value">{userData.last_activity.user_agent || '-'}</span>
          </div>
        </>
      );
    }

    return <div className="text-center">Информация о активности отсутствует</div>;
  };

  const footer = (
    <button className="btn-action" onClick={onClose}>
      <i className='bx bx-x'></i>
      Закрыть
    </button>
  );

  return (
    <Modal 
      show={show} 
      onClose={onClose} 
      title="Детали пользователя"
      footer={footer}
      size="large"
    >
      {isLoading ? (
        <div className="loading-container">Загрузка данных пользователя...</div>
      ) : (
        <>
          <div className="info-card">
            <h6 className="info-card-title">
              <i className='bx bx-user-circle'></i> Основная информация
            </h6>
            <div>{renderMainInfo()}</div>
          </div>

          <div className="info-card">
            <h6 className="info-card-title">
              <i className='bx bx-block'></i> Блокировка
            </h6>
            <div>{renderBlockingInfo()}</div>
          </div>

          <div className="info-card">
            <h6 className="info-card-title">
              <i className='bx bx-crown'></i> Подписка
            </h6>
            <div>{renderSubscriptionInfo()}</div>
          </div>

          <div className="info-card">
            <h6 className="info-card-title">
              <i className='bx bx-history'></i> История подписок
            </h6>
            <div>{renderSubscriptionHistory()}</div>
          </div>

          <div className="info-card">
            <h6 className="info-card-title">
              <i className='bx bx-link'></i> Реферальная система
            </h6>
            <div>{renderReferralInfo()}</div>
          </div>

          <div className="info-card">
            <h6 className="info-card-title">
              <i className='bx bx-history'></i> История активности
            </h6>
            <div>{renderActivityInfo()}</div>
          </div>
        </>
      )}
    </Modal>
  );
};

export default UserDetailsModal; 