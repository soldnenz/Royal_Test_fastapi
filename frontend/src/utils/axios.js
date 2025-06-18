import axios from 'axios';

// Create axios instance with base URL and default headers
const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Add request interceptor for error handling
api.interceptors.request.use(
  config => {
    // Log requests for debugging
    console.log(`Making ${config.method.toUpperCase()} request to ${config.url}`);
    const token = localStorage.getItem('token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  response => {
    return response;
  },
  error => {
    console.error('API error:', error.message);
    
    // Handle specific error cases
    if (error.response) {
      // Server responded with an error status
      console.error('Response error data:', error.response.data);
      
      // If unauthorized, potentially redirect to login
      if (error.response.status === 401) {
        console.warn('User not authenticated, consider redirecting to login');
        localStorage.removeItem('token');
        
        // НЕ редиректим на страницах присоединения к лобби (для School lobbies)
        const currentPath = window.location.pathname;
        if (!currentPath.startsWith('/multiplayer/join/')) {
          window.location.href = '/login';
        }
      }
    } else if (error.request) {
      // Request made but no response received (network error)
      console.error('Network error - no response received');
    }
    
    return Promise.reject(error);
  }
);

export default api; 