import { useEffect, useRef, useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';

const TurnstileWidget = ({ 
  sitekey = "0x4AAAAAABj8yamqHNqfr8nW", 
  onSuccess, 
  onError, 
  onExpired,
  className = "",
  size = "normal",
  theme = "auto"
}) => {
  const { theme: appTheme } = useTheme();
  const containerRef = useRef(null);
  const widgetIdRef = useRef(null);
  const [scriptLoaded, setScriptLoaded] = useState(false);
  const [scriptError, setScriptError] = useState(false);

  useEffect(() => {
    // Проверяем, не загружен ли уже скрипт
    if (window.turnstile) {
      setScriptLoaded(true);
      renderWidget();
      return;
    }

    // Проверяем, не загружается ли уже скрипт
    const existingScript = document.querySelector('script[src*="turnstile"]');
    if (existingScript) {
      existingScript.addEventListener('load', () => {
        setScriptLoaded(true);
        renderWidget();
      });
      existingScript.addEventListener('error', () => {
        setScriptError(true);
        if (onError) onError('Failed to load Turnstile script');
      });
      return;
    }

    // Загружаем Turnstile скрипт
    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    script.defer = true;
    
    script.onload = () => {
      if (window.turnstile) {
        setScriptLoaded(true);
        renderWidget();
      } else {
        setScriptError(true);
        if (onError) onError('Turnstile object not available after script load');
      }
    };

    script.onerror = () => {
      setScriptError(true);
      if (onError) onError('Failed to load Turnstile script');
    };

    document.head.appendChild(script);

    return () => {
      // Удаляем виджет если он существует
      if (window.turnstile && widgetIdRef.current) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch (error) {
          console.error('Error removing Turnstile widget:', error);
        }
      }
    };
  }, [sitekey]);

  const renderWidget = () => {
    if (!window.turnstile || !containerRef.current) {
      return;
    }

    try {
      // Определяем тему на основе приложения
      const turnstileTheme = theme === 'auto' ? (appTheme === 'dark' ? 'dark' : 'light') : theme;
      
      // Удаляем предыдущий виджет если есть
      if (widgetIdRef.current) {
        window.turnstile.remove(widgetIdRef.current);
      }
      
      widgetIdRef.current = window.turnstile.render(containerRef.current, {
        sitekey: sitekey,
        theme: turnstileTheme,
        size: size,
        callback: (token) => {
          if (onSuccess) onSuccess(token);
        },
        'error-callback': (error) => {
          console.error('Turnstile error:', error);
          if (onError) onError(error);
        },
        'expired-callback': () => {
          if (onExpired) onExpired();
        },
        'refresh-expired': 'auto',
        'refresh-timeout': 'auto',
        'retry': 'auto',
        'retry-interval': 5000
      });
    } catch (error) {
      console.error('Error rendering Turnstile widget:', error);
      if (onError) onError(error);
    }
  };

  // Обновляем тему при изменении темы приложения
  useEffect(() => {
    if (scriptLoaded && !scriptError && theme === 'auto') {
      renderWidget();
    }
  }, [appTheme, theme, scriptLoaded, scriptError]);

  if (scriptError) {
    return (
      <div className={`cf-turnstile-error ${className}`} style={{ color: 'red', textAlign: 'center', margin: '1rem 0' }}>
        Failed to load CAPTCHA. Please refresh the page or try again later.
      </div>
    );
  }

  return (
    <div 
      ref={containerRef} 
      className={`cf-turnstile ${className}`}
      style={{ 
        display: 'flex', 
        justifyContent: 'center',
        margin: '1rem 0'
      }}
    />
  );
};

export default TurnstileWidget; 