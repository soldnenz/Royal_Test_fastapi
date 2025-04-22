import { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

export const useTheme = () => {
  return useContext(ThemeContext);
};

export const ThemeProvider = ({ children }) => {
  // Get initial theme from localStorage or default to 'light'
  const [theme, setTheme] = useState(() => {
    const savedTheme = localStorage.getItem('theme');
    return savedTheme || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  });

  // Toggle theme function
  const toggleTheme = () => {
    setTheme(prevTheme => {
      const newTheme = prevTheme === 'light' ? 'dark' : 'light';
      return newTheme;
    });
  };

  // Save theme to localStorage and update document when theme changes
  useEffect(() => {
    localStorage.setItem('theme', theme);
    
    // Update the document class for global CSS theme switching
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
      // Add a custom CSS variable for light text on dark backgrounds
      document.documentElement.style.setProperty('--dark-text-color', 'rgba(255, 255, 255, 0.9)');
    } else {
      document.documentElement.classList.remove('dark');
      // Reset the custom CSS variable
      document.documentElement.style.removeProperty('--dark-text-color');
    }
  }, [theme]);

  const value = {
    theme,
    setTheme,
    toggleTheme,
    isDark: theme === 'dark',
  };

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
};

export default ThemeContext; 