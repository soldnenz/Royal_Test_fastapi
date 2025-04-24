import { createContext, useContext, useState, useEffect } from 'react';

const LanguageContext = createContext();

export const useLanguage = () => {
  return useContext(LanguageContext);
};

export const LanguageProvider = ({ children }) => {
  // Get initial language from localStorage or default to 'ru'
  const [language, setLanguage] = useState(() => {
    const savedLanguage = localStorage.getItem('language');
    // Validate the saved language is one of the supported languages
    if (savedLanguage && ['ru', 'kz', 'en'].includes(savedLanguage)) {
      return savedLanguage;
    }
    return 'ru'; // Default to Russian if saved language is invalid
  });

  // Change language function
  const changeLanguage = (lang) => {
    // Validate that lang is one of the supported languages
    if (['ru', 'kz', 'en'].includes(lang)) {
      setLanguage(lang);
    } else {
      console.warn(`Unsupported language: ${lang}, defaulting to Russian`);
      setLanguage('ru');
    }
  };

  // Save language to localStorage when it changes
  useEffect(() => {
    // Additional check to ensure language is valid before saving
    if (!['ru', 'kz', 'en'].includes(language)) {
      console.warn(`Invalid language detected: ${language}, resetting to Russian`);
      setLanguage('ru');
    } else {
      localStorage.setItem('language', language);
    }
  }, [language]);

  const value = {
    language,
    setLanguage,
    changeLanguage,
  };

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
};

export default LanguageContext; 