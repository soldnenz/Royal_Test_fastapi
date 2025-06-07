// Get current theme from localStorage or default to light
export const getCurrentTheme = () => {
  const savedTheme = localStorage.getItem('theme');
  return savedTheme === 'dark' ? 'dark' : 'light';
};

// Check if current theme is dark
export const isDarkTheme = () => {
  return getCurrentTheme() === 'dark';
};

// Toggle theme
export const toggleTheme = () => {
  const currentTheme = getCurrentTheme();
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  
  // Save theme to localStorage
  localStorage.setItem('theme', newTheme);
  
  // Apply theme to document
  applyTheme(newTheme);
  
  // Dispatch a custom event so components can react to theme changes
  window.dispatchEvent(new Event('themeChange'));
  
  return newTheme;
};

// Set specific theme
export const setTheme = (theme) => {
  const validTheme = theme === 'dark' ? 'dark' : 'light';
  
  // Save theme to localStorage
  localStorage.setItem('theme', validTheme);
  
  // Apply theme to document
  applyTheme(validTheme);
  
  // Dispatch a custom event so components can react to theme changes
  window.dispatchEvent(new Event('themeChange'));
  
  return validTheme;
};

// Apply theme to document
export const applyTheme = (theme) => {
  if (theme === 'dark') {
    // Apply dark-theme class for custom CSS variables
    document.documentElement.classList.add('dark-theme');
    document.body.classList.add('dark-theme');
    
    // Apply dark class for Tailwind CSS
    document.documentElement.classList.add('dark');
    
    document.documentElement.style.setProperty('--text-color', 'rgba(255, 255, 255, 0.9)');
    document.documentElement.style.setProperty('--bg-color', '#1e1e2d');
  } else {
    // Remove dark-theme class for custom CSS variables
    document.documentElement.classList.remove('dark-theme');
    document.body.classList.remove('dark-theme');
    
    // Remove dark class for Tailwind CSS
    document.documentElement.classList.remove('dark');
    
    document.documentElement.style.setProperty('--text-color', 'rgba(0, 0, 0, 0.9)');
    document.documentElement.style.setProperty('--bg-color', '#ffffff');
  }
};

// Initialize theme on page load
export const initTheme = () => {
  const theme = getCurrentTheme();
  applyTheme(theme);
}; 