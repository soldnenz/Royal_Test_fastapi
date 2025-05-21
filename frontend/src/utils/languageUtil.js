import { testTranslations } from '../translations/testTranslations';

// Available languages
export const LANGUAGES = {
  ru: 'Русский',
  kz: 'Қазақша',
  en: 'English'
};

// Get current language from localStorage or default to Russian
export const getCurrentLanguage = () => {
  const savedLanguage = localStorage.getItem('language');
  return savedLanguage && Object.keys(LANGUAGES).includes(savedLanguage) 
    ? savedLanguage 
    : 'ru';
};

// Set language in localStorage
export const setLanguage = (lang) => {
  if (Object.keys(LANGUAGES).includes(lang)) {
    localStorage.setItem('language', lang);
    
    // Update html lang attribute for accessibility
    document.documentElement.lang = lang;
    
    // Dispatch a custom event so components can react to language changes
    window.dispatchEvent(new Event('languageChange'));
    
    return true;
  }
  return false;
};

// Get a specific translation key based on current language
export const getTranslation = (key, section = 'test') => {
  const language = getCurrentLanguage();
  
  // Select translations based on section
  let translations;
  if (section === 'test') {
    translations = testTranslations;
  } else {
    // Default to test translations for now
    translations = testTranslations;
  }
  
  // Return translation or key as fallback
  return translations[language]?.[key] || 
         translations['ru']?.[key] || 
         key;
};

// Localize multilingual object based on current language
export const localizeText = (textObj) => {
  if (!textObj) return '';
  if (typeof textObj === 'string') return textObj;
  
  const language = getCurrentLanguage();
  return textObj[language] || textObj.ru || '';
}; 