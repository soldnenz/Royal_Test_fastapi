import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../../shared/config';
import LoadingSpinner from '../../shared/components/LoadingSpinner';
import ErrorDisplay from '../../shared/components/ErrorDisplay';
import { useToast, TOAST_TYPES } from '../../shared/ToastContext';

const TestsList = ({ onEditQuestion }) => {
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedUid, setExpandedUid] = useState(null);
  const [expandedDetails, setExpandedDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [progressPercentage, setProgressPercentage] = useState(0);
  const [displayLanguage, setDisplayLanguage] = useState('ru'); // Default display language
  const { showToast } = useToast();

  // Helper function to extract text from multilingual object
  const getTextFromMultilingual = (textObj, language = displayLanguage) => {
    if (!textObj) return '';
    
    if (typeof textObj === 'string') {
      return textObj;
    }
    
    // Try to get text in selected language or fall back to Russian
    return textObj[language] || textObj.ru || '';
  };

  // Fetch all questions on component mount
  useEffect(() => {
    fetchAllQuestions();
  }, []);

  const fetchAllQuestions = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API_BASE_URL}/api/tests/all`, {
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.status === 'ok' && Array.isArray(data.data)) {
        // Store raw data, handle multilingual display in the render
        setQuestions(data.data);
      } else {
        throw new Error(data.message || 'Ошибка при загрузке данных');
      }
    } catch (err) {
      const errorMessage = `Не удалось загрузить вопросы: ${err.message}`;
      setError(errorMessage);
      showToast(errorMessage, TOAST_TYPES.ERROR);
      console.error('Error fetching questions:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchQuestionDetails = async (uid) => {
    // If already expanded, just close it
    if (expandedUid === uid) {
      setExpandedUid(null);
      return;
    }
    
    setExpandedUid(uid);
    setLoadingDetails(true);
    setProgressPercentage(0);
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/tests/by_uid/${uid}`, {
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      // Stream response to show progress
      const reader = response.body.getReader();
      const contentLength = response.headers.get('Content-Length');
      let receivedLength = 0;
      const chunks = [];
      
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          break;
        }
        
        chunks.push(value);
        receivedLength += value.length;
        
        if (contentLength) {
          setProgressPercentage((receivedLength / contentLength) * 100);
        }
      }
      
      // Combine the chunks into a single response
      const chunksAll = new Uint8Array(receivedLength);
      let position = 0;
      for (const chunk of chunks) {
        chunksAll.set(chunk, position);
        position += chunk.length;
      }
      
      const resultText = new TextDecoder('utf-8').decode(chunksAll);
      const parsedData = JSON.parse(resultText);
      
      // Extract the question data (it might be nested in a "data" property)
      const questionData = parsedData.data || parsedData;
      setExpandedDetails(questionData);
    } catch (err) {
      const errorMessage = `Ошибка при загрузке деталей: ${err.message}`;
      showToast(errorMessage, TOAST_TYPES.ERROR);
      console.error('Error fetching question details:', err);
      setExpandedUid(null);
    } finally {
      setLoadingDetails(false);
      setProgressPercentage(100);
    }
  };

  const handleDeleteQuestion = async (uid) => {
    if (!confirm('Вы уверены, что хотите удалить этот вопрос?')) {
      return;
    }
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/tests/${uid}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      // Remove the deleted question from the local state
      setQuestions(questions.filter(q => q.uid !== uid));
      
      // If the deleted question was expanded, clear the expanded state
      if (expandedUid === uid) {
        setExpandedUid(null);
        setExpandedDetails(null);
      }
      
      showToast('Вопрос успешно удален', TOAST_TYPES.SUCCESS);
    } catch (err) {
      const errorMessage = `Ошибка при удалении вопроса: ${err.message}`;
      showToast(errorMessage, TOAST_TYPES.ERROR);
      console.error('Error deleting question:', err);
    }
  };

  // Language selector component
  const LanguageSelector = () => (
    <div className="language-selector">
      <button
        type="button"
        className={`language-btn ${displayLanguage === 'ru' ? 'active' : ''}`}
        onClick={() => setDisplayLanguage('ru')}
      >
        Русский
      </button>
      <button
        type="button"
        className={`language-btn ${displayLanguage === 'kz' ? 'active' : ''}`}
        onClick={() => setDisplayLanguage('kz')}
      >
        Қазақша
      </button>
      <button
        type="button"
        className={`language-btn ${displayLanguage === 'en' ? 'active' : ''}`}
        onClick={() => setDisplayLanguage('en')}
      >
        English
      </button>
    </div>
  );

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error && questions.length === 0) {
    return (
      <div className="error-display-wrapper">
        <ErrorDisplay message={error} onRetry={fetchAllQuestions} />
      </div>
    );
  }

  return (
    <div className="questions-list">
      <div className="list-header">
        <div className="list-header-row">
          <h2>Всего вопросов: {questions.length}</h2>
          <LanguageSelector />
        </div>
      </div>
      
      {questions.length === 0 ? (
        <div className="empty-state">
          <p>Нет доступных вопросов. Создайте первый вопрос.</p>
        </div>
      ) : (
        questions.map(question => (
          <div key={question.uid} className="question-card">
            <div className="question-header">
              <h3>{getTextFromMultilingual(question.question_text)}</h3>
              <div className="question-actions">
                <button 
                  className="action-button"
                  onClick={() => fetchQuestionDetails(question.uid)}
                >
                  {expandedUid === question.uid ? 'Скрыть' : 'Подробнее'}
                </button>
                <button 
                  className="action-button edit"
                  onClick={() => onEditQuestion(question.uid)}
                >
                  Редактировать
                </button>
                <button 
                  className="action-button delete"
                  onClick={() => handleDeleteQuestion(question.uid)}
                >
                  Удалить
                </button>
              </div>
            </div>
            
            <div className="question-meta">
              Категории: {question.categories.join(', ')} | 
              Медиа: {question.has_media ? '✅' : '❌'}
              <div className="question-uid">UID: {question.uid}</div>
            </div>
            
            {/* Details section */}
            {expandedUid === question.uid && (
              <div className={`question-details visible`}>
                {loadingDetails ? (
                  <div className="progress-bar">
                    <div 
                      className="progress-bar-inner" 
                      style={{ width: `${progressPercentage}%` }}
                    ></div>
                  </div>
                ) : expandedDetails ? (
                  <QuestionDetails details={expandedDetails} language={displayLanguage} />
                ) : (
                  <p>Не удалось загрузить детали.</p>
                )}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
};

// Helper component to display question details
const QuestionDetails = ({ details, language = 'ru' }) => {
  // Helper function to extract text from multilingual object
  const getText = (textObj) => {
    if (!textObj) return '';
    if (typeof textObj === 'string') return textObj;
    return textObj[language] || textObj.ru || '';
  };

  return (
    <div>
      <p><strong>Вопрос:</strong> {getText(details.question_text)}</p>
      <p><strong>Пояснение:</strong> {getText(details.explanation)}</p>
      <p><strong>Правильный ответ:</strong> {details.correct_label}</p>
      
      {details.options && Array.isArray(details.options) && (
        <>
          <p><strong>Варианты ответа:</strong></p>
          <ul>
            {details.options.map((opt, idx) => (
              <li 
                key={idx} 
                className={`question-option ${opt.label === details.correct_label ? 'correct' : ''}`}
              >
                <strong>{opt.label}:</strong> {getText(opt.text)}
              </li>
            ))}
          </ul>
        </>
      )}
      
      <p><strong>Категории:</strong> {details.categories?.join(', ') || '-'}</p>
      
      {details.pdd_section_uids && details.pdd_section_uids.length > 0 && (
        <p><strong>Разделы ПДД:</strong> {details.pdd_section_uids.join(', ')}</p>
      )}
      
      <p><strong>ID:</strong> {details.id}</p>
      <p><strong>UID:</strong> {details.uid}</p>
      <p><strong>Создано:</strong> {details.created_at}</p>
      {details.updated_at && <p><strong>Обновлено:</strong> {details.updated_at}</p>}
      
      {/* Display media if available */}
      {details.media_file_base64 && details.media_filename && (
        <div className="media-preview">
          {details.media_filename.endsWith('.mp4') ? (
            <video 
              controls 
              src={`data:video/mp4;base64,${details.media_file_base64}`}
            ></video>
          ) : (
            <img 
              src={`data:image/*;base64,${details.media_file_base64}`} 
              alt="Медиа контент"
            />
          )}
        </div>
      )}
    </div>
  );
};

export default TestsList; 