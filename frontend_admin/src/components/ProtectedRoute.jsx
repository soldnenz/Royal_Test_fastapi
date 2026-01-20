import React, { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';

const ProtectedRoute = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(null);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        // Используем абсолютный путь для запроса через nginx
        const apiUrl = window.location.origin + '/api/users/me';
        console.log('Checking auth at:', apiUrl);
        
        const response = await fetch(apiUrl, {
          method: 'GET',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        console.log('Auth response status:', response.status);

        if (response.ok) {
          const data = await response.json();
          console.log('Auth data:', data);
          const user = data.data;
          
          // Проверяем, является ли пользователь админом
          if (user.role === 'admin' || user.role === 'moderator' || user.role === 'tests_creator') {
            console.log('User is admin:', user.role);
            setIsAdmin(true);
            setIsAuthenticated(true);
          } else {
            console.log('User is not admin:', user.role);
            setIsAuthenticated(false);
          }
        } else {
          console.log('Auth failed, response not ok');
          setIsAuthenticated(false);
        }
      } catch (error) {
        console.error('Auth check failed:', error);
        setIsAuthenticated(false);
      }
    };

    checkAuth();
  }, []);

  // Пока проверяем авторизацию, показываем загрузку
  if (isAuthenticated === null) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh',
        fontSize: '18px',
        color: '#666'
      }}>
        Проверка авторизации...
      </div>
    );
  }

  // Если не авторизован или не админ, редирект на главную
  if (!isAuthenticated || !isAdmin) {
    // Редирект на главный сайт
    window.location.href = '/';
    return null;
  }

  return children;
};

export default ProtectedRoute;
