import React from 'react';
import './UsersList.css';

const UsersList = ({ 
  users, 
  onShowDetails, 
  onShowBalance, 
  onShowSubscription, 
  onShowEditSubscription, 
  onShowBan 
}) => {
  if (!users || users.length === 0) {
    return (
      <div className="table-responsive">
        <table className="table">
          <thead>
            <tr>
              <th>ИИН</th>
              <th>Имя</th>
              <th>Email</th>
              <th>Телефон</th>
              <th>Статус подписки</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan="6" className="text-center">Пользователи не найдены</td>
            </tr>
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="table-responsive">
      <table className="table">
        <thead>
          <tr>
            <th>ИИН</th>
            <th>Имя</th>
            <th>Email</th>
            <th>Телефон</th>
            <th>Статус подписки</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {users.map(user => {
            const isBanned = user.status === 'banned';
            return (
              <tr key={user.id} className={isBanned ? 'banned-user' : ''}>
                <td>{user.id}</td>
                <td>
                  <div className="user-name">
                    {user.name || `${user.firstName || ''} ${user.lastName || ''}`}
                    {isBanned && <span className="ban-badge">ЗАБЛОКИРОВАН</span>}
                  </div>
                </td>
                <td>{user.email}</td>
                <td>{user.phone || 'Нет данных'}</td>
                <td>
                  {user.subscription ? (
                    <div className={`badge badge-${user.subscription.status === 'active' ? 'success' : 'warning'}`}>
                      <span className="subscription-type">
                        <i className='bx bx-check-circle'></i>
                        {user.subscription.type || 'Стандарт'}
                      </span>
                      <span className="sub-info">
                        До: {new Date(user.subscription.expiresAt).toLocaleDateString()}
                      </span>
                    </div>
                  ) : (
                    <div className="badge badge-secondary">
                      <i className='bx bx-x-circle'></i>
                      Нет подписки
                    </div>
                  )}
                </td>
                <td>
                  <div className="action-buttons">
                    <button
                      className="btn-action"
                      onClick={() => onShowDetails(user)}
                      title="Детали пользователя"
                    >
                      <i className='bx bx-user'></i>
                      <span>Детали</span>
                    </button>
                    
                    <button
                      className="btn-action"
                      onClick={() => onShowBalance(user)}
                      title="Управление балансом"
                    >
                      <i className='bx bx-wallet'></i>
                      <span>Баланс</span>
                    </button>
                    
                    <button
                      className="btn-action"
                      onClick={() => onShowSubscription(user)}
                      title="Просмотр подписки"
                    >
                      <i className='bx bx-credit-card'></i>
                      <span>Подписка</span>
                    </button>
                    
                    <button
                      className="btn-action"
                      onClick={() => onShowEditSubscription(user)}
                      title="Редактировать подписку"
                    >
                      <i className='bx bx-edit'></i>
                      <span>Изменить</span>
                    </button>
                    
                    <button
                      className={`btn-action ${isBanned ? 'btn-success' : 'btn-danger'}`}
                      onClick={() => onShowBan(user)}
                      title={isBanned ? "Разблокировать пользователя" : "Заблокировать пользователя"}
                    >
                      <i className={`bx ${isBanned ? 'bx-check-circle' : 'bx-block'}`}></i>
                      <span>{isBanned ? 'Разблокировать' : 'Блокировать'}</span>
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default UsersList; 