import React, { createContext, useState, useContext } from 'react';

// Create context
const LoaderContext = createContext({
  loading: false,
  setLoading: () => {},
});

// Provider component
export const LoaderProvider = ({ children }) => {
  const [loading, setLoading] = useState(false);

  return (
    <LoaderContext.Provider value={{ loading, setLoading }}>
      {loading && (
        <div className="global-loader">
          <div className="loader-overlay"></div>
          <div className="loader-content">
            <div className="spinner"></div>
            <p>Загрузка...</p>
          </div>
        </div>
      )}
      {children}
    </LoaderContext.Provider>
  );
};

// Hook for using the loader context
export const useLoader = () => useContext(LoaderContext); 