import React, { useEffect, useState } from 'react';
import './ThemeToggle.css';

const ThemeToggle = () => {
  const [isDarkTheme, setIsDarkTheme] = useState(
    document.documentElement.getAttribute('data-theme') === 'dark'
  );

  useEffect(() => {
    // Инициализируем тему при загрузке
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    setIsDarkTheme(savedTheme === 'dark');
  }, []);

  const toggleTheme = () => {
    const newTheme = isDarkTheme ? 'light' : 'dark';
    setIsDarkTheme(!isDarkTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
  };

  return (
    <button 
      className="theme-toggle icon-btn" 
      onClick={toggleTheme} 
      aria-label={isDarkTheme ? 'Включить светлую тему' : 'Включить темную тему'}
      title={isDarkTheme ? 'Включить светлую тему' : 'Включить темную тему'}
    >
      {isDarkTheme ? (
        <i className="bx bx-sun"></i>
      ) : (
        <i className="bx bx-moon"></i>
      )}
    </button>
  );
};

export default ThemeToggle; 