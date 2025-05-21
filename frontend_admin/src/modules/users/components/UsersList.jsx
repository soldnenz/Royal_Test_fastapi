import React, { useState, useRef, useEffect } from 'react';
import './UsersList.css';

const UsersList = ({ 
  users, 
  onShowDetails, 
  onShowBalance, 
  onShowSubscription, 
  onShowEditSubscription, 
  onShowBan 
}) => {
  const [scrolledRight, setScrolledRight] = useState(false);
  const tableRef = useRef(null);

  useEffect(() => {
    const handleScroll = () => {
      if (tableRef.current) {
        const { scrollLeft } = tableRef.current;
        setScrolledRight(scrollLeft > 100);
      }
    };

    const tableElement = tableRef.current;
    if (tableElement) {
      tableElement.addEventListener('scroll', handleScroll);
    }

    return () => {
      if (tableElement) {
        tableElement.removeEventListener('scroll', handleScroll);
      }
    };
  }, []);

  if (!users || users.length === 0) {
    return (
      <div className="table-responsive">
        <table className="table">
          <thead>
            <tr>
              <th>ИИН</th>
              <th className="sticky-column">ФИО</th>
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
    <>
      {scrolledRight && (
        <div className="floating-name-container">
          {users.map((user, index) => {
            const fullName = user.full_name || user.name || `${user.firstName || ''} ${user.lastName || ''}`;
            const isBanned = user.is_banned || user.status === 'banned';
            
            return (
              <div 
                key={`floating-${user.id}`} 
                className={`floating-name ${isBanned ? 'banned-user' : ''}`}
                style={{ top: `${(index + 1) * 61}px` }}
              >
                {fullName}
                {isBanned && <span className="ban-badge-small">!</span>}
              </div>
            );
          })}
        </div>
      )}
      <div className="table-responsive" ref={tableRef}>
        <table className="table">
          <thead>
            <tr>
              <th>ИИН</th>
              <th className="sticky-column">ФИО</th>
              <th>Email</th>
              <th>Телефон</th>
              <th>Статус подписки</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {users.map(user => {
              const isBanned = user.is_banned || user.status === 'banned';
              const fullName = user.full_name || user.name || `${user.firstName || ''} ${user.lastName || ''}`;
              
              return (
                <tr key={user.id} className={isBanned ? 'banned-user' : ''}>
                  <td>{user.iin || user.id}</td>
                  <td className="sticky-column">
                    <div className="user-name">
                      {fullName}
                      {isBanned && <span className="ban-badge">ЗАБЛОКИРОВАН</span>}
                    </div>
                  </td>
                  <td>{user.email}</td>
                  <td>{user.phone || 'Нет данных'}</td>
                  <td>
                    {user.subscription ? (
                      <div className={`badge badge-${user.subscription.is_active || user.subscription.status === 'active' ? 'success' : 'warning'}`}>
                        <span className="subscription-type">
                          <i className='bx bx-check-circle'></i>
                          {user.subscription.subscription_type || user.subscription.type || 'Стандарт'}
                        </span>
                        <span className="sub-info">
                          {user.subscription.expires_at || user.subscription.expiresAt ? 
                            `До: ${new Date(user.subscription.expires_at || user.subscription.expiresAt).toLocaleDateString()}` :
                            'Срок не определен'
                          }
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
                      
                      {!user.subscription && (
                        <button
                          className="btn-action"
                          onClick={() => onShowSubscription(user)}
                          title="Добавить подписку"
                        >
                          <i className='bx bx-credit-card'></i>
                          <span>Добавить подписку</span>
                        </button>
                      )}
                      
                      {user.subscription && (
                        <button
                          className="btn-action"
                          onClick={() => onShowEditSubscription(user)}
                          title="Изменить подписку"
                        >
                          <i className='bx bx-edit'></i>
                          <span>Изменить подписку</span>
                        </button>
                      )}
                      
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
    </>
  );
};

export default UsersList; 