import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  FaStar, FaCheck, FaTimes, FaClock, FaChartBar, FaUser, FaLightbulb,
  FaArrowLeft, FaHistory, FaExclamationTriangle, FaTrophy, FaBullseye,
  FaBookOpen, FaRedo, FaDownload, FaShare, FaEye, FaEyeSlash
} from 'react-icons/fa';
import api from '../utils/axios';
import DashboardHeader from '../components/dashboard/DashboardHeader';
import DashboardSidebar from '../components/dashboard/DashboardSidebar';
import { getCurrentTheme, toggleTheme, initTheme } from '../utils/themeUtil';
import { useLanguage } from '../contexts/LanguageContext';
import { translations } from '../translations/translations';
import { localizeText } from '../utils/languageUtil';
import './TestResultsPage.css';

const TestResultsPage = () => {
  const { lobbyId } = useParams();
  const navigate = useNavigate();
  const { language } = useLanguage();
  const t = translations[language];
  const [theme, setTheme] = useState(getCurrentTheme());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [profileData, setProfileData] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [showDetailedAnswers, setShowDetailedAnswers] = useState(false);
  
  const isDarkTheme = theme === 'dark';

  // Initialize theme
  useEffect(() => {
    initTheme();
    document.body.classList.toggle('dark-theme', theme === 'dark');
  }, []);

  // Handle theme changes
  useEffect(() => {
    const handleThemeChange = () => {
      const newTheme = getCurrentTheme();
      setTheme(newTheme);
      document.body.classList.toggle('dark-theme', newTheme === 'dark');
    };
    
    window.addEventListener('themeChange', handleThemeChange);
    return () => window.removeEventListener('themeChange', handleThemeChange);
  }, []);

  // Theme toggle
  const handleToggleTheme = () => {
    const newTheme = toggleTheme();
    setTheme(newTheme);
    document.body.classList.toggle('dark-theme', newTheme === 'dark');
  };

  // Load profile data
  useEffect(() => {
    const fetchProfileData = async () => {
      try {
        const response = await api.get('/users/me');
        if (response.data.status === "ok") {
          setProfileData(response.data.data);
        }
      } catch (err) {
        console.error('Error fetching profile data:', err);
      }
    };

    fetchProfileData().catch(() => {
      console.log("Profile data fetch failed silently");
    });
  }, []);

  // Toggle sidebar
  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);

  // Fetch test results
  useEffect(() => {
    const fetchResults = async () => {
      try {
        setLoading(true);
        const response = await api.get(`/test-stats/${lobbyId}/secure/results`);
        
        if (response.data.status === "ok") {
          setResults(response.data.data);
        } else {
          setError(response.data.message || 'Failed to load test results');
        }
      } catch (err) {
        console.error('Error fetching test results:', err);
        setError(err.response?.data?.message || 'Failed to load test results');
      } finally {
        setLoading(false);
      }
    };

    if (lobbyId) {
      fetchResults();
    }
  }, [lobbyId]);

  // Format time
  const formatTime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hours > 0) {
      return `${hours}:${minutes < 10 ? '0' : ''}${minutes}:${secs < 10 ? '0' : ''}${secs}`;
    }
    return `${minutes}:${secs < 10 ? '0' : ''}${secs}`;
  };

  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return t.notSpecified || 'Не указано';
    const date = new Date(dateStr);
    return date.toLocaleDateString(language === 'en' ? 'en-US' : language === 'kz' ? 'kz-KZ' : 'ru-RU', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Translate functions
  const getTestTypeText = (testType) => {
    const testTypeTranslations = {
      'exam': t.exam || 'Экзамен',
      'practice': t.practice || 'Практика'
    };
    return testTypeTranslations[testType] || testType;
  };

  const getSkillLevelText = (skillLevel) => {
    const skillTranslations = {
      'excellent': t.excellent || 'Отлично',
      'very_good': t.veryGood || 'Очень хорошо',
      'good': t.good || 'Хорошо',
      'satisfactory': t.satisfactory || 'Удовлетворительно',
      'needs_improvement': t.needsImprovement || 'Требует улучшения',
      'poor': t.poor || 'Плохо',
      'not_determined': t.notDetermined || 'Не определен'
    };
    return skillTranslations[skillLevel] || skillLevel;
  };

  const getSpeedRatingText = (speedRating) => {
    const speedTranslations = {
      'very_fast': t.veryFast || 'Очень быстро',
      'fast': t.fast || 'Быстро',
      'normal': t.normal || 'Нормально',
      'slow': t.slow || 'Медленно',
      'very_slow': t.verySlow || 'Очень медленно',
      'not_determined': t.notDetermined || 'Не определена'
    };
    return speedTranslations[speedRating] || speedRating;
  };

  const getStrengthText = (strength) => {
    if (typeof strength === 'string') return strength;
    
    switch (strength.type) {
      case 'correct_answers':
        return `${t.correctAnswers || 'Правильных ответов'}: ${strength.count}`;
      case 'test_passed':
        return t.testPassedSuccessfully || 'Тест пройден успешно';
      case 'fast_completion':
        return `${t.fastCompletion || 'Быстрое выполнение'}: ${strength.avg_time}с`;
      default:
        return strength.type;
    }
  };

  const getImprovementText = (area) => {
    if (typeof area === 'string') {
      const areaTranslations = {
        'test_not_started': t.testNotStarted || 'Начать прохождение теста'
      };
      return areaTranslations[area] || area;
    }
    
    switch (area.type) {
      case 'unanswered_questions':
        return `${t.unansweredQuestions || 'Не отвечено на'} ${area.count} ${t.questions || 'вопросов'}`;
      case 'incorrect_answers':
        return `${t.incorrectAnswers || 'Неправильных ответов'}: ${area.count}`;
      case 'slow_completion':
        return `${t.slowCompletion || 'Медленное выполнение'}: ${area.avg_time}с`;
      default:
        return area.type;
    }
  };

  const getRecommendationText = (recommendation) => {
    const recommendationTranslations = {
      'answer_all_questions': t.answerAllQuestions || 'Постарайтесь отвечать на все вопросы',
      'excellent_work': t.excellentWork || 'Отличная работа! Продолжайте в том же духе',
      'additional_study_needed': t.additionalStudyNeeded || 'Рекомендуется дополнительное изучение материала',
      'practice_time_management': t.practiceTimeManagement || 'Практикуйте управление временем',
      'complete_test_for_results': t.completeTestForResults || 'Пройдите тест полностью для получения результатов'
    };
    return recommendationTranslations[recommendation] || recommendation;
  };

  const getDisplayName = (userInfo) => {
    if (userInfo.full_name && userInfo.full_name.trim()) {
      return userInfo.full_name;
    }
    if (userInfo.username && userInfo.username.trim()) {
      return userInfo.username;
    }
    if (userInfo.email && userInfo.email.trim()) {
      return userInfo.email;
    }
    return t.user || 'Пользователь';
  };

  const getSkillColor = (skillLevel) => {
    switch (skillLevel) {
      case 'excellent': return isDarkTheme ? '#ffd700' : '#d4af37';
      case 'very_good': return isDarkTheme ? '#ffd700' : '#d4af37';
      case 'good': return isDarkTheme ? '#e6c200' : '#b8941f';
      case 'satisfactory': return '#f59e0b';
      case 'needs_improvement': return '#f59e0b';
      case 'poor': return '#ef4444';
      default: return 'var(--text-secondary)';
    }
  };

  // Navigation functions
  const handleReturnToDashboard = () => {
    navigate('/dashboard');
  };

  const handleRetakeTest = () => {
    navigate('/dashboard/tests');
  };



  // Loading state
  if (loading) {
    return (
      <div className={`app-container ${isDarkTheme ? 'dark-theme' : ''}`}>
        <DashboardHeader 
          profileData={profileData} 
          toggleSidebar={toggleSidebar} 
          isSidebarOpen={isSidebarOpen} 
          onToggleTheme={handleToggleTheme}
          currentTheme={theme}
        />
        <DashboardSidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
        
        <div className={`main-content ${isSidebarOpen ? 'sidebar-open' : ''}`}>
          <div className="loading-container">
            <div className="loading-bar-container">
              <div className="loading-bar"></div>
            </div>
            <div className="loading-text">{t.loadingResults || 'Загрузка результатов...'}</div>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`app-container ${isDarkTheme ? 'dark-theme' : ''}`}>
        <DashboardHeader 
          profileData={profileData} 
          toggleSidebar={toggleSidebar} 
          isSidebarOpen={isSidebarOpen} 
          onToggleTheme={handleToggleTheme}
          currentTheme={theme}
        />
        <DashboardSidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
        
        <div className={`main-content ${isSidebarOpen ? 'sidebar-open' : ''}`}>
          <div className="error-container">
            <FaTimes size={48} style={{ color: '#ef4444', marginBottom: '20px' }} />
            <h2 style={{ marginBottom: '16px' }}>{t.error || 'Ошибка'}</h2>
            <p style={{ marginBottom: '32px', textAlign: 'center' }}>{error}</p>
            <button className="btn btn-primary" onClick={handleReturnToDashboard}>
              {t.returnToDashboard || 'Вернуться к панели управления'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!results) {
    return null;
  }

  const { lobby_info, user_info, test_results, detailed_answers, category_performance, performance_analytics } = results;
  const isPassed = test_results.passed;
  const percentage = Math.round(test_results.percentage);
  const skillColor = getSkillColor(performance_analytics.skill_level);

  return (
    <div className={`app-container ${isDarkTheme ? 'dark-theme' : ''}`}>
      <DashboardHeader 
        profileData={profileData} 
        toggleSidebar={toggleSidebar} 
        isSidebarOpen={isSidebarOpen} 
        onToggleTheme={handleToggleTheme}
        currentTheme={theme}
      />
      <DashboardSidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
      
      <div className={`main-content ${isSidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="test-results-page">
          {/* Header */}
          <div className="results-page-header">
            <button className="back-button" onClick={handleReturnToDashboard}>
              <FaArrowLeft />
              {t.backToDashboard || 'Назад к панели управления'}
            </button>
            
            <div className="header-info">
              <h1 className="page-title">{t.testResults || 'Результаты теста'}</h1>
              <div className="test-info">
                <span className="test-type">{getTestTypeText(lobby_info.test_type)}</span>
                <span className="test-date">{formatDate(lobby_info.finished_at)}</span>
              </div>
            </div>
          </div>

          {/* Main Results Card */}
          <div className="results-hero">
            <div className="hero-left">
              <div className={`result-status ${isPassed ? 'passed' : 'failed'}`}>
                <div className="status-icon">
                  {isPassed ? <FaTrophy /> : <FaTimes />}
                </div>
                <div className="status-text">
                  <h2>{isPassed ? (t.testPassed || 'ТЕСТ ПРОЙДЕН') : (t.testFailed || 'ТЕСТ НЕ ПРОЙДЕН')}</h2>
                  <p>{getSkillLevelText(performance_analytics.skill_level)}</p>
                </div>
              </div>
              
              <div className="quick-stats">
                <div className="stat">
                  <span className="stat-value">{test_results.correct_count}</span>
                  <span className="stat-label">{t.correct || 'Правильно'}</span>
                </div>
                <div className="stat">
                  <span className="stat-value">{test_results.incorrect_count}</span>
                  <span className="stat-label">{t.incorrect || 'Неправильно'}</span>
                </div>
                <div className="stat">
                  <span className="stat-value">{test_results.unanswered_count}</span>
                  <span className="stat-label">{t.skipped || 'Пропущено'}</span>
                </div>
              </div>
            </div>
            
            <div className="hero-right">
              <div className="score-circle" style={{ borderColor: skillColor }}>
                <div className="score-percentage" style={{ color: skillColor }}>
                  {percentage}%
                </div>
                <div className="score-description">
                  {test_results.correct_count} из {test_results.total_questions}
                </div>
              </div>
            </div>
          </div>

          {/* Analytics Grid */}
          <div className="analytics-grid">
            {/* Performance Overview */}
            <div className="analytics-card">
              <div className="card-header">
                <FaChartBar className="card-icon" />
                <h3>{t.overallAnalysis || 'Общий анализ'}</h3>
              </div>
              <div className="card-content">
                <div className="performance-metrics">
                  <div className="metric">
                    <span className="metric-label">{t.accuracy || 'Точность'}</span>
                    <div className="metric-bar">
                      <div 
                        className="metric-fill" 
                        style={{ width: `${percentage}%`, backgroundColor: skillColor }}
                      ></div>
                    </div>
                    <span className="metric-value">{percentage}%</span>
                  </div>
                  
                  <div className="metric">
                    <span className="metric-label">{t.completion || 'Завершенность'}</span>
                    <div className="metric-bar">
                      <div 
                        className="metric-fill" 
                        style={{ width: `${test_results.completion_rate}%`, backgroundColor: 'var(--primary)' }}
                      ></div>
                    </div>
                    <span className="metric-value">{Math.round(test_results.completion_rate)}%</span>
                  </div>
                  
                  <div className="performance-summary">
                    <div className="summary-item">
                      <FaBullseye className="summary-icon" />
                      <span>{t.level || 'Уровень'}: {getSkillLevelText(performance_analytics.skill_level)}</span>
                    </div>
                    <div className="summary-item">
                      <FaClock className="summary-icon" />
                      <span>{t.speed || 'Скорость'}: {getSpeedRatingText(performance_analytics.speed_rating)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Time Analysis */}
            <div className="analytics-card">
              <div className="card-header">
                <FaClock className="card-icon" />
                <h3>{t.timeAnalysis || 'Анализ времени'}</h3>
              </div>
              <div className="card-content">
                <div className="time-stats">
                  <div className="time-stat">
                    <span className="time-label">{t.totalTime || 'Общее время'}</span>
                    <span className="time-value">{formatTime(test_results.duration_seconds)}</span>
                  </div>
                  <div className="time-stat">
                    <span className="time-label">{t.averagePerQuestion || 'Среднее на вопрос'}</span>
                    <span className="time-value">{test_results.average_time_per_question}с</span>
                  </div>
                  {lobby_info.exam_mode && (
                    <div className="time-stat">
                      <span className="time-label">{t.timeLimit || 'Лимит времени'}</span>
                      <span className="time-value">{lobby_info.max_time_minutes} {t.minutes || 'мин'}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Recommendations */}
            <div className="analytics-card">
              <div className="card-header">
                <FaLightbulb className="card-icon" />
                <h3>{t.recommendations || 'Рекомендации'}</h3>
              </div>
              <div className="card-content">
                <div className="recommendations">
                  {performance_analytics.strengths.length > 0 && (
                    <div className="recommendation-section">
                      <h4 className="section-title success">{t.strengths || 'Сильные стороны'}</h4>
                      <ul className="recommendation-list">
                        {performance_analytics.strengths.map((strength, index) => (
                          <li key={index} className="recommendation-item success">
                            <FaCheck className="recommendation-icon" />
                            {getStrengthText(strength)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {performance_analytics.areas_for_improvement.length > 0 && (
                    <div className="recommendation-section">
                      <h4 className="section-title warning">{t.areasForImprovement || 'Области для улучшения'}</h4>
                      <ul className="recommendation-list">
                        {performance_analytics.areas_for_improvement.map((area, index) => (
                          <li key={index} className="recommendation-item warning">
                            <FaExclamationTriangle className="recommendation-icon" />
                            {getImprovementText(area)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {performance_analytics.recommendations.length > 0 && (
                    <div className="recommendation-section">
                      <h4 className="section-title info">{t.tips || 'Советы'}</h4>
                      <ul className="recommendation-list">
                        {performance_analytics.recommendations.map((rec, index) => (
                          <li key={index} className="recommendation-item info">
                            <FaLightbulb className="recommendation-icon" />
                            {getRecommendationText(rec)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Session Info */}
            <div className="analytics-card">
              <div className="card-header">
                <FaUser className="card-icon" />
                <h3>{t.testInfo || 'Информация о тесте'}</h3>
              </div>
              <div className="card-content">
                <div className="session-info">
                  <div className="info-item">
                    <span className="info-label">{t.user || 'Пользователь'}</span>
                    <span className="info-value">{getDisplayName(user_info)}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">{t.testType || 'Тип теста'}</span>
                    <span className="info-value">{getTestTypeText(lobby_info.test_type)}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">{t.completionDate || 'Дата прохождения'}</span>
                    <span className="info-value">{formatDate(lobby_info.finished_at)}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">{t.passingScore || 'Проходной балл'}</span>
                    <span className="info-value">70%</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">{t.testId || 'ID теста'}</span>
                    <span className="info-value">{lobby_info.lobby_id}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Detailed Answers Section */}
          {detailed_answers && detailed_answers.length > 0 && (
            <div className="detailed-answers-section">
              <div className="section-header">
                <h3>{t.detailedAnswerReview || 'Детальный разбор ответов'}</h3>
                <div className="section-controls">
                  <button 
                    className="toggle-button"
                    onClick={() => setShowDetailedAnswers(!showDetailedAnswers)}
                  >
                    {showDetailedAnswers ? <FaEyeSlash /> : <FaEye />}
                    {showDetailedAnswers ? (t.hide || 'Скрыть') : (t.show || 'Показать')}
                  </button>
                </div>
              </div>

              {showDetailedAnswers && (
                <div className="answers-grid">
                  {detailed_answers.map((answer, index) => (
                    <div 
                      key={index} 
                      className={`answer-card ${answer.is_answered ? (answer.is_correct ? 'correct' : 'incorrect') : 'unanswered'}`}
                    >
                      <div className="answer-header">
                        <span className="question-number">{t.question || 'Вопрос'} {answer.question_number}</span>
                        <div className="answer-status">
                          {!answer.is_answered ? (
                            <span className="status unanswered">{t.notAnswered || 'Не отвечен'}</span>
                          ) : answer.is_correct ? (
                            <FaCheck className="status-icon correct" />
                          ) : (
                            <FaTimes className="status-icon incorrect" />
                          )}
                        </div>
                      </div>
                      
                      <div className="question-text">
                        {localizeText(answer.question_text)}
                      </div>
                      
                      <div className="answer-options">
                        {answer.options.map((option, optIndex) => {
                          let optionClass = 'answer-option';
                          if (optIndex === answer.correct_answer_index) {
                            optionClass += ' correct-answer';
                          }
                          if (optIndex === answer.user_answer_index) {
                            optionClass += answer.is_correct ? ' user-correct' : ' user-incorrect';
                          }
                          
                          return (
                            <div key={optIndex} className={optionClass}>
                              <span className="option-label">{String.fromCharCode(65 + optIndex)}</span>
                              <span className="option-text">{localizeText(option)}</span>
                            </div>
                          );
                        })}
                      </div>
                      
                      {answer.explanation && Object.keys(answer.explanation).length > 0 && (
                        <div className="answer-explanation">
                          <strong>{t.explanation || 'Объяснение'}</strong>
                          <p>{localizeText(answer.explanation)}</p>
                        </div>
                      )}
                      
                      {answer.categories.length > 0 && (
                        <div className="answer-categories">
                          {answer.categories.map((cat, catIndex) => (
                            <span key={catIndex} className="category-tag">{cat}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Action Buttons */}
          <div className="results-actions">
            <button className="btn btn-secondary" onClick={handleReturnToDashboard}>
              <FaArrowLeft />
              {t.returnToDashboard || 'Вернуться к панели управления'}
            </button>
            
            <button className="btn btn-primary" onClick={handleRetakeTest}>
              <FaRedo />
              {t.retakeTest || 'Пройти тест заново'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TestResultsPage; 