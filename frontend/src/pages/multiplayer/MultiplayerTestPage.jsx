import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  FaTimes, FaCheck, FaArrowLeft, FaArrowRight, FaFlag, 
  FaLanguage, FaMoon, FaSun, FaHistory, FaExclamationTriangle,
  FaPlay, FaPause, FaVolumeUp, FaVolumeMute, FaExpand,
  FaBars, FaQuestionCircle, FaLightbulb, FaClock, FaStar, FaChartBar, FaUser,
  FaUsers, FaCrown, FaTimesCircle
} from 'react-icons/fa';
import api from '../../utils/axios';
import DashboardHeader from '../../components/dashboard/DashboardHeader';
import DashboardSidebar from '../../components/dashboard/DashboardSidebar';
import { getCurrentTheme, toggleTheme, initTheme } from '../../utils/themeUtil';
import { getCurrentLanguage, setLanguage, getTranslation, localizeText, LANGUAGES } from '../../utils/languageUtil';
import useMultiplayerTestWebSocket from '../../hooks/useMultiplayerTestWebSocket';
import { notify } from '../../components/notifications/NotificationSystem';
import '../dashboard/styles.css';
import '../TestPage.css';
import './MultiplayerTestPage.css';

const MultiplayerTestPage = () => {
  const { lobbyId } = useParams();
  const navigate = useNavigate();
  
  // Theme and language state
  const [theme, setTheme] = useState(getCurrentTheme());
  const [language, setCurrentLanguage] = useState(getCurrentLanguage());
  
  // Loading and error states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Test state - similar to TestPage
  const [questions, setQuestions] = useState(() => {
    // Пытаемся восстановить questions из localStorage при инициализации
    const savedQuestions = localStorage.getItem(`questions_${lobbyId}`);
    if (savedQuestions) {
      try {
        const parsedQuestions = JSON.parse(savedQuestions);
        if (Array.isArray(parsedQuestions) && parsedQuestions.length > 0) {
          console.log('Initialized questions from localStorage:', parsedQuestions);
          return parsedQuestions;
        }
      } catch (e) {
        console.error('Error parsing saved questions on init:', e);
      }
    }
    return [];
  });
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(() => {
    const savedIndex = localStorage.getItem(`currentQuestionIndex_${lobbyId}`);
    return savedIndex ? parseInt(savedIndex, 10) : 0;
  });
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [userAnswers, setUserAnswers] = useState({});
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [answerSubmitted, setAnswerSubmitted] = useState(false);
  const [correctAnswer, setCorrectAnswer] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const [afterAnswerMedia, setAfterAnswerMedia] = useState(null);
  const [lobbyInfo, setLobbyInfo] = useState(null);
  const [timeLeft, setTimeLeft] = useState(40 * 60);
  const [mediaLoading, setMediaLoading] = useState(false);
  const [isExamMode, setIsExamMode] = useState(false);
  const [testCompleted, setTestCompleted] = useState(false);
  const [testResults, setTestResults] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isQuestionNavOpen, setIsQuestionNavOpen] = useState(false);
  const [profileData, setProfileData] = useState(null);
  const [videoError, setVideoError] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportData, setReportData] = useState({ type: '', description: '' });
  const [reportSubmitting, setReportSubmitting] = useState(false);
  const [videoProgress, setVideoProgress] = useState(0);
  const [videoLoading, setVideoLoading] = useState(false);
  
  // Multiplayer-specific state
  const [currentUser, setCurrentUser] = useState(null);
  const [isHost, setIsHost] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  
  // Refs
  const intervalRef = useRef(null);
  const videoRef = useRef(null);
  const afterVideoRef = useRef(null);
  const videoIntervalRef = useRef(null);
  const videoProgressRef = useRef(null);
  const questionsRef = useRef(questions);
  const currentQuestionIndexRef = useRef(currentQuestionIndex);
  const userAnswersRef = useRef(userAnswers);
  const isDarkTheme = theme === 'dark';

  // Track participants currently being kicked so their button becomes inactive immediately
  const [kickingIds, setKickingIds] = useState({});

  // Update refs when state changes to ensure WebSocket handlers have access to current values
  useEffect(() => {
    questionsRef.current = questions;
  }, [questions]);

  useEffect(() => {
    currentQuestionIndexRef.current = currentQuestionIndex;
  }, [currentQuestionIndex]);

  useEffect(() => {
    userAnswersRef.current = userAnswers;
  }, [userAnswers]);

  // Define all functions before WebSocket hook to avoid hoisting issues
  const handleReturnToDashboard = () => {
    navigate('/dashboard');
  };

  // Fetch test results function - defined as regular function to avoid hoisting issues
  const fetchTestResults = useCallback(async () => {
    try {
      const response = await api.get(`/lobbies/lobbies/${lobbyId}/results`);
      
      if (response.data.status === "ok") {
        setTestResults(response.data.data);
        localStorage.removeItem(`exam_timer_${lobbyId}`);
        localStorage.removeItem(`userAnswers_${lobbyId}`);
        localStorage.removeItem(`currentQuestionIndex_${lobbyId}`);
      } else {
        setError(response.data.message || 'Failed to load test results');
      }
    } catch (err) {
      console.error('Error fetching test results:', err);
      
      if (err.response?.status === 404 || 
          (err.response?.data?.message && err.response?.data?.message.includes("не активен"))) {
        // Получаем актуальную длину questions из localStorage или используем 0
        const savedQuestions = localStorage.getItem(`questions_${lobbyId}`);
        let questionsLength = 0;
        if (savedQuestions) {
          try {
            questionsLength = JSON.parse(savedQuestions).length;
          } catch (e) {
            questionsLength = 0;
          }
        }
        
        setTestResults({
          user_result: {
            correct_count: 0,
            total_questions: questionsLength,
            percentage: 0,
            passed: false
          }
        });
        
        localStorage.removeItem(`exam_timer_${lobbyId}`);
        localStorage.removeItem(`userAnswers_${lobbyId}`);
        localStorage.removeItem(`currentQuestionIndex_${lobbyId}`);
      } else {
        const errMsg = err.response?.data?.message || '';
        if (err.response?.status === 403 && errMsg.includes('не являетесь участником')) {
          notify.error(errMsg);
          navigate('/dashboard');
        } else {
          setError(errMsg || 'Failed to load test results');
        }
      }
    }
  }, [lobbyId, navigate]);

  const handleAnswerSubmit = async (answerIndex) => {
    if (answerSubmitted) {
      console.log('Answer already submitted for this question');
      return;
    }
    
    // Validate input parameters
    if (typeof answerIndex !== 'number' || answerIndex < 0) {
      console.error('Invalid answer index:', answerIndex);
      notify.error('Ошибка: неверный индекс ответа');
      return;
    }
    
    const questionId = questions[currentQuestionIndex];
    if (!questionId) {
      console.error('No current question ID available');
      notify.error('Ошибка: вопрос не найден');
      return;
    }
    
    // Ensure question ID is a string
    const questionIdStr = String(questionId);
    
    // Check if user already answered this question (double check)
    if (userAnswers[questionIdStr] !== undefined) {
      console.log('User already answered this question in userAnswers');
      setAnswerSubmitted(true);
      setSelectedAnswer(userAnswers[questionIdStr]);
      return;
    }
    
    setSelectedAnswer(answerIndex);
    setSyncing(true);
    
    const updatedAnswers = { ...userAnswers, [questionIdStr]: answerIndex };
    
    setAnswerSubmitted(true);
    setUserAnswers(updatedAnswers);
    localStorage.setItem(`userAnswers_${lobbyId}`, JSON.stringify(updatedAnswers));
    
    console.log('Submitting answer:', {
      question_id: questionIdStr,
      answer_index: answerIndex,
      lobby_id: lobbyId,
      user_id: currentUser?.id,
      question_type: typeof questionIdStr,
      answer_type: typeof answerIndex
    });
    
    try {
      const response = await api.post(`/lobbies/lobbies/${lobbyId}/answer`, {
        question_id: questionIdStr,
        answer_index: parseInt(answerIndex, 10) // Ensure it's an integer
      });
      
      if (response.data.status === "ok") {
        console.log('Answer submitted successfully:', response.data);
        
        // Show success notification
        notify.success(getTranslation('answerSubmittedSuccessfully') || 'Answer submitted successfully');
        
        // В мультиплеере правильный ответ показывается только по команде хоста
        // Но мы можем показать пользователю, что он ответил
        if (!isExamMode) {
          // Показываем индикацию того, что ответ отправлен
          // Правильный ответ будет показан хостом через WebSocket
        }
      }
    } catch (err) {
      console.error('Error submitting answer:', err);
      console.error('Error details:', {
        status: err.response?.status,
        data: err.response?.data,
        message: err.message
      });
      
      // Handle 403 error
      if (err.response?.status === 403) {
        const errorMessage = err.response?.data?.message || 'Access denied';
        notify.error(`${getTranslation('cannotSubmitAnswer') || 'Cannot submit answer'}: ${errorMessage}`);
      } else if (err.response?.status === 400) {
        const errorMessage = err.response?.data?.message || 'Invalid answer data';
        console.error('Bad request error:', err.response?.data);
        
        // Specific handling for duplicate answer error
        if (errorMessage.includes('уже ответили') || errorMessage.includes('already answered')) {
          console.log('User tried to submit duplicate answer - updating UI state');
          // Don't show error notification for duplicate answer - it's expected behavior
          // Just ensure the UI state is consistent
          notify.info('Вы уже ответили на этот вопрос');
        } else {
          notify.error(`${getTranslation('errorSubmittingAnswer') || 'Error submitting answer'}: ${errorMessage}`);
          
          // Revert answer state on other 400 errors
          setAnswerSubmitted(false);
          setSelectedAnswer(null);
          const revertedAnswers = { ...userAnswers };
          delete revertedAnswers[questionIdStr];
          setUserAnswers(revertedAnswers);
          localStorage.setItem(`userAnswers_${lobbyId}`, JSON.stringify(revertedAnswers));
        }
      } else {
        notify.error(getTranslation('errorSubmittingAnswer') || 'Error submitting answer');
        setError(err.response?.data?.message || 'Failed to submit your answer');
        
        // Revert answer state on server errors
        setAnswerSubmitted(false);
        setSelectedAnswer(null);
        const revertedAnswers = { ...userAnswers };
        delete revertedAnswers[questionIdStr];
        setUserAnswers(revertedAnswers);
        localStorage.setItem(`userAnswers_${lobbyId}`, JSON.stringify(revertedAnswers));
      }
    } finally {
      setSyncing(false);
    }
  };

  // Host control functions
  const handleHostNextQuestion = async () => {
    if (!isHost) {
      notify.error(getTranslation('onlyHostCanControl') || 'Only host can control the test');
      return;
    }

    try {
      setSyncing(true);
      const response = await api.post(`/lobbies/lobbies/${lobbyId}/next-question`);
      
      if (response.data.status === 'ok') {
        notify.action(getTranslation('movedToNextQuestion') || 'Moved to next question');
      }
    } catch (error) {
      console.error('Error moving to next question:', error);
      notify.error(error.response?.data?.message || getTranslation('errorMovingToNextQuestion') || 'Error moving to next question');
    } finally {
      setSyncing(false);
    }
  };

  const handleHostFinishTest = async () => {
    if (!isHost) {
      notify.error(getTranslation('onlyHostCanControl') || 'Only host can control the test');
      return;
    }

    try {
      setSyncing(true);
      const response = await api.post(`/lobbies/lobbies/${lobbyId}/finish-test`);
      
      if (response.data.status === 'ok') {
        notify.host(getTranslation('testFinishedByHost') || 'Test finished by host', {
          title: '🏁 Тест завершен'
        });
        
        setTestCompleted(true);
        fetchTestResults();
      }
    } catch (error) {
      console.error('Error finishing test:', error);
      notify.error(error.response?.data?.message || getTranslation('errorFinishingTest') || 'Error finishing test');
    } finally {
      setSyncing(false);
    }
  };

  // handleSyncState сохраняем для возможного использования, но больше не показываем всплывающие уведомления
  const handleSyncState = async () => {
    if (!isHost) return;
    try {
      await api.post(`/lobbies/lobbies/${lobbyId}/sync-state`);
    } catch (error) {
      console.error('Error syncing state:', error);
    }
  };

  const handleShowCorrectAnswer = async () => {
    if (!isHost) {
      notify.error(getTranslation('onlyHostCanControl') || 'Only host can control the test');
      return;
    }

    // Проверяем, что у нас есть текущий вопрос
    if (currentQuestionIndex < 0 || currentQuestionIndex >= questions.length || !questions[currentQuestionIndex]) {
      notify.warning('Нет текущего вопроса для показа ответа');
      return;
    }

    const currentQuestionId = questions[currentQuestionIndex];
    console.log('Showing correct answer for:', {
      questionIndex: currentQuestionIndex,
      questionId: currentQuestionId,
      totalQuestions: questions.length
    });

    try {
      const response = await api.post(`/lobbies/lobbies/${lobbyId}/show-correct-answer`, {
        question_id: currentQuestionId,
        question_index: currentQuestionIndex
      });
      
      if (response.data.status === 'ok') {
        notify.answer(getTranslation('correctAnswerShown') || 'Correct answer shown to all participants', {
          title: '💡 Правильный ответ показан'
        });
        
        console.log('Correct answer shown successfully');
      }
    } catch (error) {
      console.error('Error showing correct answer:', error);
      notify.error(error.response?.data?.message || getTranslation('errorShowingCorrectAnswer') || 'Error showing correct answer');
    }
  };

  // Handle kicking participant - defined before WebSocket hook to avoid hoisting issues
  const handleKickParticipant = useCallback(async (participantId, participantName) => {
    if (!confirm(`Вы уверены, что хотите исключить ${participantName}?`)) {
      return;
    }
    
    // Immediately mark this participant as "kicking" so the button becomes disabled
    setKickingIds(prev => ({ ...prev, [participantId]: true }));
    
    try {
      setSyncing(true);
      const response = await api.post(`/lobbies/lobbies/${lobbyId}/kick`, {
        target_user_id: participantId
      });
      
      if (response.data.status === 'ok') {
        notify.host(`${participantName} исключен из лобби`, {
          title: '👤 Участник исключен'
        });
      }
    } catch (error) {
      console.error('Error kicking participant:', error);
      notify.error('Ошибка при исключении участника');
      
      // Rollback kicking state on error
      setKickingIds(prev => {
        const next = { ...prev };
        delete next[participantId];
        return next;
      });
    } finally {
      setSyncing(false);
    }
  }, [lobbyId]);

  // Fetch current question with 403 error handling - moved up to avoid hoisting issues
  const fetchCurrentQuestion = useCallback(async () => {
    if (!questions.length || currentQuestionIndex >= questions.length) return;
    
    const questionId = questions[currentQuestionIndex];
    
    try {
      setMediaLoading(true);
      setVideoError(false);
      
      const response = await api.get(`/lobbies/lobbies/${lobbyId}/questions/${questionId}`);
      
      if (response.data.status === "ok") {
        const questionData = response.data.data;
        
        // Обработка основного медиа файла
        if (questionData.has_media && questionData.media_file_id) {
          const mediaUrl = `/api/lobbies/files/media/${questionId}?t=${Date.now()}`;
          questionData.media_url = mediaUrl;
        } else {
          // Нет медиа - будем показывать заглушку
          questionData.media_url = null;
        }
        
        setCurrentQuestion(questionData);
        setAnswerSubmitted(false);
        setSelectedAnswer(null);
        setCorrectAnswer(null);
        setExplanation(null);
        setAfterAnswerMedia(null);
        
        // Проверяем, отвечал ли пользователь на этот вопрос
        const userAnswer = userAnswers[questionId];
        if (userAnswer !== undefined) {
          console.log(`Восстанавливаем ответ пользователя на вопрос ${questionId}: ${userAnswer}`);
          setSelectedAnswer(userAnswer);
          setAnswerSubmitted(true);
          
          // В мультиплеере правильный ответ показывается только по команде хоста
          // Но если пользователь уже видел правильный ответ, восстанавливаем его
          const shouldShowAnswer = !isExamMode;
          
          if (shouldShowAnswer) {
            // В мультиплеере не показываем правильный ответ автоматически
            // Он будет показан только когда хост отправит команду
            console.log('Ответ пользователя восстановлен, ожидаем команды хоста для показа правильного ответа');
          }
        } else {
          console.log(`Пользователь еще не отвечал на вопрос ${questionId}`);
        }
        
        setMediaLoading(false);
      } else {
        setError(response.data.message || 'Failed to load question');
        setMediaLoading(false);
      }
    } catch (err) {
      console.error('Error fetching question:', err);
      
      if (err.response?.status === 403) {
        const errorMessage = err.response?.data?.message || 'Access denied';
        
        notify.error(errorMessage);

        if (errorMessage.includes('не являетесь участником')) {
          navigate('/dashboard');
          return;
        }

        console.warn('403 error handled:', errorMessage);
      } else {
        setError(err.response?.data?.message || 'Failed to load question');
      }
      setMediaLoading(false);
    }
  }, [lobbyId, questions, currentQuestionIndex, userAnswers, isExamMode, navigate]);

  // Define helper functions before they are used to avoid hoisting issues
  const fetchAfterAnswerMedia = useCallback(async (questionId) => {
    try {
      setMediaLoading(true);
      
      // Сначала получаем данные вопроса чтобы найти after_answer_media_file_id
      const questionResponse = await api.get(`/lobbies/lobbies/${lobbyId}/questions/${questionId}`);
      if (questionResponse.data.status === "ok") {
        const questionData = questionResponse.data.data;
        const afterMediaFileId = questionData.after_answer_media_file_id || questionData.after_answer_media_id;
        
        if (afterMediaFileId) {
          const mediaUrl = `/api/lobbies/files/after-answer-media/${questionId}?lobby_id=${lobbyId}&t=${Date.now()}`;
          setAfterAnswerMedia(mediaUrl);
          console.log('Setting after answer media from fetchAfterAnswerMedia:', mediaUrl);
        } else {
          // Нет дополнительного медиа
          setAfterAnswerMedia(null);
          console.log('No after answer media file ID found');
        }
      } else {
        console.error('Failed to get question data for after answer media');
        setAfterAnswerMedia(null);
      }
      setMediaLoading(false);
    } catch (err) {
      console.error('Error fetching after-answer media:', err);
      setAfterAnswerMedia(null);
      setMediaLoading(false);
    }
  }, [lobbyId]);

  const fetchCorrectAnswer = useCallback(async (questionId) => {
    try {
      const response = await api.get(`/lobbies/lobbies/${lobbyId}/correct-answer`, {
        params: { question_id: questionId }
      });
      
      if (response.data.status === "ok") {
        setCorrectAnswer(response.data.data.correct_index);
        setExplanation(response.data.data.explanation);
        
        if (response.data.data.has_after_media) {
          fetchAfterAnswerMedia(questionId);
        }
      }
    } catch (err) {
      console.error('Error fetching correct answer:', err);
    }
  }, [lobbyId, fetchAfterAnswerMedia]);

  // Define functions used in JSX before WebSocket hook to avoid hoisting issues
  const handleToggleTheme = () => {
    const newTheme = toggleTheme();
    setTheme(newTheme);
    document.body.classList.toggle('dark-theme', newTheme === 'dark');
  };

  const handleChangeLanguage = (newLanguage) => {
    if (setLanguage(newLanguage)) {
      setCurrentLanguage(newLanguage);
      window.dispatchEvent(new Event('languageChange'));
    }
  };

  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);
  const toggleQuestionNav = () => setIsQuestionNavOpen(!isQuestionNavOpen);
  const closeQuestionNav = () => setIsQuestionNavOpen(false);

  const handleNextQuestion = () => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    }
  };

  const handlePrevQuestion = () => {
    if (currentQuestionIndex > 0) {
      const newIndex = currentQuestionIndex - 1;
      setCurrentQuestionIndex(newIndex);
      setAnswerSubmitted(true);
      setSelectedAnswer(userAnswers[questions[newIndex]]);
      setCorrectAnswer(null);
      setExplanation(null);
      setAfterAnswerMedia(null);
      setVideoError(false);
      setVideoProgress(0);
      
      const shouldShowAnswer = !isExamMode;
      if (shouldShowAnswer) {
        fetchCorrectAnswer(questions[newIndex]);
      }
    }
  };

  const finishTest = async () => {
    try {
      setSyncing(true);
      
      const response = await api.post(`/lobbies/lobbies/${lobbyId}/finish`, {});
      
      if (response.data.status === "ok") {
        setTestCompleted(true);
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
        
        // Note: sendMessage will be used for WebSocket notifications
        
        notify.success(getTranslation('testCompletedSuccessfully') || 'Test completed successfully', {
          title: '🎉 Тест завершен'
        });
        fetchTestResults();
      }
    } catch (err) {
      console.error('Error finishing test:', err);
      
      if (err.response?.status === 400 && 
          (err.response?.data?.message?.includes("не активен") || 
           err.response?.data?.message?.includes("уже завершен"))) {
        console.log("Test already finished");
        setTestCompleted(true);
        
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
        
        fetchTestResults();
      } else {
        notify.error(getTranslation('errorFinishingTest') || 'Error finishing test');
        setError(err.response?.data?.message || 'Failed to finish test');
      }
    } finally {
      setSyncing(false);
    }
  };

  const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds < 10 ? '0' : ''}${remainingSeconds}`;
  };

  // Helper function for processing correct answer
  const processCorrectAnswer = useCallback((questionsArray, questionIndex, userAnswers, data) => {
    const { question_id, question_index, correct_answer_index, explanation, has_after_media, after_answer_media_file_id } = data;
    const receivedQuestionId = String(question_id);
    const receivedQuestionIndex = typeof question_index === 'number' ? question_index : -1;
    
    // Проверяем по индексу в первую очередь, потом по ID
    let targetQuestionId = null;
    let isValidQuestion = false;
    
    if (receivedQuestionIndex >= 0 && receivedQuestionIndex < questionsArray.length) {
      targetQuestionId = String(questionsArray[receivedQuestionIndex]);
      isValidQuestion = (targetQuestionId === receivedQuestionId);
      console.log('Checking by index:', {
        receivedIndex: receivedQuestionIndex,
        questionAtIndex: targetQuestionId,
        receivedQuestionId,
        matches: isValidQuestion
      });
    }
    
    // Если не найдено по индексу, проверяем по текущему вопросу
    if (!isValidQuestion && questionIndex >= 0 && questionsArray[questionIndex]) {
      const currentQuestionId = String(questionsArray[questionIndex]);
      isValidQuestion = (currentQuestionId === receivedQuestionId);
      targetQuestionId = currentQuestionId;
      console.log('Checking by current question:', {
        currentIndex: questionIndex,
        currentQuestionId,
        receivedQuestionId,
        matches: isValidQuestion
      });
    }
    
    console.log('Show correct answer comparison:', {
      receivedQuestionId,
      receivedIndex: receivedQuestionIndex,
      currentIndex: questionIndex,
      targetQuestionId,
      isValidQuestion,
      questionsLength: questionsArray.length
    });
    
    if (isValidQuestion) {
      console.log('Applying correct answer for question:', targetQuestionId);
      
      // Если это ответ для будущего вопроса, сначала обновляем индекс
      if (receivedQuestionIndex >= 0 && receivedQuestionIndex !== questionIndex) {
        console.log(`Updating question index from ${questionIndex} to ${receivedQuestionIndex} before showing answer`);
        setCurrentQuestionIndex(receivedQuestionIndex);
        localStorage.setItem(`currentQuestionIndex_${lobbyId}`, receivedQuestionIndex.toString());
        
        // Проверяем, есть ли сохраненный ответ для этого вопроса
        if (userAnswers[targetQuestionId] !== undefined) {
          setSelectedAnswer(userAnswers[targetQuestionId]);
        }
      }
      
      setCorrectAnswer(correct_answer_index);
      setExplanation(explanation);
      
      if (has_after_media && after_answer_media_file_id) {
        const mediaUrl = `/api/lobbies/files/after-answer-media/${question_id}?lobby_id=${lobbyId}&t=${Date.now()}`;
        setAfterAnswerMedia(mediaUrl);
        console.log('Setting after answer media URL:', mediaUrl);
      } else {
        setAfterAnswerMedia(null);
      }
      
      setAnswerSubmitted(true);
    } else {
      console.warn('Received correct answer for different question - ignoring:', {
        received: receivedQuestionId,
        receivedIndex: receivedQuestionIndex,
        currentIndex: questionIndex,
        targetQuestionId
      });
    }
  }, [lobbyId]);

  // Initialize WebSocket connection - moved after all callback functions are defined
  const webSocketHook = useMultiplayerTestWebSocket(lobbyId, {
    onAnswerReceived: (data) => {
      console.log('Answer received in page:', data);
    },
    onShowCorrectAnswer: (data) => {
      console.log('Received show_correct_answer message:', { type: 'show_correct_answer', data });
      console.log('Received correct answer data:', data);
      const { question_id, question_index, correct_answer_index, explanation, has_after_media, after_answer_media_type, after_answer_media_file_id } = data;
      
      // Используем refs для получения актуального состояния
      const currentQuestions = questionsRef.current;
      const currentIndex = currentQuestionIndexRef.current;
      const currentUserAnswers = userAnswersRef.current;
      
      // Если questions пустой, пытаемся восстановить из localStorage один раз
      if (currentQuestions.length === 0) {
        console.log('Questions array is empty, attempting to restore from localStorage');
        const savedQuestions = localStorage.getItem(`questions_${lobbyId}`);
        if (savedQuestions) {
          try {
            const parsedQuestions = JSON.parse(savedQuestions);
            if (Array.isArray(parsedQuestions) && parsedQuestions.length > 0) {
              console.log('Restored questions from localStorage:', parsedQuestions.length);
              setQuestions(parsedQuestions);
              // Обновляем ref немедленно
              questionsRef.current = parsedQuestions;
              // Используем восстановленные questions для дальнейшей обработки
              processCorrectAnswer(parsedQuestions, currentIndex, currentUserAnswers);
              return;
            }
          } catch (e) {
            console.error('Error parsing saved questions:', e);
          }
        }
        console.warn('Cannot apply correct answer - no questions available');
        return;
      }
      
             processCorrectAnswer(currentQuestions, currentIndex, currentUserAnswers, data);
    },
    onNextQuestion: (data) => {
      console.log('Next question received:', data);
      const { question_id, question_index } = data;
      
      if (typeof question_index === 'number' && question_index >= 0) {
        console.log(`Moving to question index ${question_index} from ${currentQuestionIndex}`);
        
        // Только сбрасываем состояние если мы действительно переходим к НОВОМУ вопросу
        if (question_index !== currentQuestionIndex) {
          setAnswerSubmitted(false);
          setSelectedAnswer(null);
          setCorrectAnswer(null);
          setExplanation(null);
          setAfterAnswerMedia(null);
          setVideoError(false);
          setVideoProgress(0);
        }
        
        setCurrentQuestionIndex(question_index);
        localStorage.setItem(`currentQuestionIndex_${lobbyId}`, question_index.toString());
        
        // Используем актуальные questions (возможно восстановленные из localStorage)
        const questionsToUse = questionsRef.current;
        if (questionsToUse.length > question_index) {
          const newQuestionId = String(questionsToUse[question_index]);
          if (newQuestionId && userAnswers[newQuestionId] !== undefined) {
            console.log(`Restoring saved answer for question ${newQuestionId}: ${userAnswers[newQuestionId]}`);
            setSelectedAnswer(userAnswers[newQuestionId]);
            setAnswerSubmitted(true);
          }
          
          // Сразу загружаем новый вопрос для синхронизации
          console.log('Immediately fetching new question after next_question message');
          setTimeout(() => {
            fetchCurrentQuestion().catch(err => {
              console.error('Error fetching question after next_question:', err);
            });
          }, 100); // Небольшая задержка для обновления состояния
        }
      }
    },
    onTestFinished: (data) => {
      console.log('Test finished by host:', data);
      setTestCompleted(true);
      fetchTestResults();
    },
    onSync: ({ question_index, question_id, forced_sync, show_correct_answer, show_participant_answers, correct_answer_index, explanation }) => {
      console.log('Sync callback received:', { question_index, question_id, forced_sync, show_correct_answer, show_participant_answers, correct_answer_index, explanation });
      setSyncing(false);
      
      console.log('Sync comparison:', {
        receivedIndex: question_index,
        currentIndex: currentQuestionIndex,
        receivedQuestionId: question_id,
        currentQuestionId: questions[currentQuestionIndex],
        needsUpdate: question_index !== currentQuestionIndex,
        questionsLength: questions.length
      });
      
      if (typeof question_index === 'number' && question_index !== currentQuestionIndex) {
        console.log(`Syncing question index from ${currentQuestionIndex} to ${question_index}`);
        
        setAnswerSubmitted(false);
        setSelectedAnswer(null);
        // НЕ сбрасываем correctAnswer автоматически при синхронизации
        // setCorrectAnswer(null); 
        setExplanation(null);
        setAfterAnswerMedia(null);
        setVideoError(false);
        setVideoProgress(0);
        setCurrentQuestionIndex(question_index);
        localStorage.setItem(`currentQuestionIndex_${lobbyId}`, question_index.toString());
        
        if (questions.length > 0 && userAnswers) {
          const newQuestionId = String(question_id || questions[question_index]);
          if (newQuestionId && userAnswers[newQuestionId] !== undefined) {
            console.log(`Restoring user answer for synced question ${newQuestionId}: ${userAnswers[newQuestionId]}`);
            setSelectedAnswer(userAnswers[newQuestionId]);
            setAnswerSubmitted(true);
          }
        }
      } else if (question_index === currentQuestionIndex) {
        console.log('Question index already synchronized');
        
        // Если мы на том же вопросе, но получили информацию о показе правильного ответа,
        // и правильный ответ еще не показан локально - устанавливаем его и объяснение
        if (show_correct_answer && correctAnswer === null && typeof correct_answer_index === 'number') {
          console.log('Sync indicates correct answer should be shown, setting correct answer index and explanation:', { correct_answer_index, explanation });
          setCorrectAnswer(correct_answer_index);
          if (explanation) {
            setExplanation(explanation);
          }
          
          // Проверяем, отвечал ли пользователь на этот вопрос
          const currentQuestionId = String(question_id || questions[question_index]);
          if (currentQuestionId && userAnswers[currentQuestionId] !== undefined) {
            console.log(`Restoring answer submitted state for question ${currentQuestionId}: ${userAnswers[currentQuestionId]}`);
            setSelectedAnswer(userAnswers[currentQuestionId]);
            setAnswerSubmitted(true);
          }
        }
      }
    }
  });
  
  // Destructure with safety checks
  const { 
    participants = [], 
    isConnected = false, 
    sendMessage = null,
    connectionError = null,
    getParticipantAnswerForQuestion = null,
    hasParticipantAnswered = null
  } = webSocketHook || {};

  // Get valid participants for display using useMemo to prevent re-filtering on every render
  const validParticipants = useMemo(() => {
    if (!Array.isArray(participants)) {
      return [];
    }
    return participants.filter(participant => 
      participant && 
      typeof participant === 'object' &&
      participant.id &&
      participant.name && 
      typeof participant.name === 'string' &&
      participant.name.trim() !== '' && 
      participant.name !== 'Unknown User' &&
      !participant.name.includes('undefined')
    );
  }, [participants]);

  // Render participant card function - defined after WebSocket hook but before use
  const renderParticipantCard = useCallback((participant, index) => {
    // Safety checks
    if (!participant || !participant.id || !currentQuestion) {
      return null;
    }

    const isKicking = Boolean(kickingIds[participant.id]);
    const currentQIdForLookup = questions[currentQuestionIndex] ? String(questions[currentQuestionIndex]) : null;
    const participantHasAnswered = hasParticipantAnswered && currentQIdForLookup ? hasParticipantAnswered(participant.id, currentQIdForLookup) : false;
    const participantAnswerValue = getParticipantAnswerForQuestion && currentQIdForLookup ? getParticipantAnswerForQuestion(participant.id, currentQIdForLookup) : null;
    
    return (
      <div 
        key={participant.id || `participant-${index}`} 
        className={`participant-card ${
          participant.id === currentUser?.id ? 'current-user' : ''
        } ${
          participantHasAnswered ? 'answered' : ''
        }`}
      >
        <div className="participant-avatar">
          {participant.name ? participant.name.charAt(0).toUpperCase() : '?'}
        </div>
        <div className="participant-info">
          <div className="participant-name">
            {participant.name || 'Unknown'}
            {participant.is_host && <FaCrown className="host-icon" />}
            {participant.id === currentUser?.id && <FaUser className="current-user-icon" />}
          </div>
          <div className="participant-status">
            {participantHasAnswered ? (
              <div className="participant-answer-info">
                <span className="answered-text">{getTranslation('answered')}</span>
                {isHost && participantAnswerValue !== null && typeof participantAnswerValue === 'number' && (
                  <span className="answer-choice">
                    Вариант {String.fromCharCode(65 + participantAnswerValue)}
                  </span>
                )}
              </div>
            ) : (
              <span className="thinking-text">{getTranslation('thinking')}</span>
            )}
          </div>
        </div>
        
        {/* Kick button for host */}
        {isHost && participant.id !== currentUser?.id && !isKicking && (
          <button 
            className="kick-btn"
            onClick={() => handleKickParticipant(participant.id, participant.name)}
            disabled={isKicking}
            title={`Исключить ${participant.name}`}
          >
            <FaTimesCircle />
          </button>
        )}
        
        {isHost && participant.id !== currentUser?.id && isKicking && (
          <div className="kick-btn" style={{ opacity: 0.4, cursor: 'not-allowed' }}>
            <FaTimesCircle />
          </div>
        )}
        
        <div className={`participant-connection-dot ${participant.online ? 'online' : 'offline'}`}></div>
      </div>
    );
  }, [currentQuestion, hasParticipantAnswered, getParticipantAnswerForQuestion, isHost, currentUser, handleKickParticipant, kickingIds, questions, currentQuestionIndex]);

  // Connection status update
  useEffect(() => {
    if (isConnected) {
      setConnectionStatus('connected');
    } else if (connectionError) {
      setConnectionStatus('error');
    } else {
      setConnectionStatus('connecting');
    }
  }, [isConnected, connectionError]);

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

  // Handle language changes
  useEffect(() => {
    const handleLanguageChange = () => {
      setCurrentLanguage(getCurrentLanguage());
    };
    
    window.addEventListener('languageChange', handleLanguageChange);
    return () => window.removeEventListener('languageChange', handleLanguageChange);
  }, []);

  // Save current question index
  useEffect(() => {
    localStorage.setItem(`currentQuestionIndex_${lobbyId}`, currentQuestionIndex.toString());
  }, [currentQuestionIndex, lobbyId]);

  // Load profile data
  useEffect(() => {
    const fetchProfileData = async () => {
      try {
        const response = await api.get('/users/me');
        if (response.data.status === "ok") {
          setProfileData(response.data.data);
          setCurrentUser(response.data.data);
        }
      } catch (err) {
        console.error('Error fetching profile data:', err);
      }
    };

    fetchProfileData().catch(() => {
      console.log("Profile data fetch failed silently");
    });
  }, []);

  // Video progress tracking (same as TestPage)
  const updateVideoProgress = useCallback((video) => {
    if (!video || video.duration === 0) return;
    const progress = (video.currentTime / video.duration) * 100;
    setVideoProgress(progress);
  }, []);

  // Advanced video management (same as TestPage)
  const setupVideoAutoplay = useCallback((video) => {
    if (!video) return;

    if (videoIntervalRef.current) {
      clearInterval(videoIntervalRef.current);
    }
    if (videoProgressRef.current) {
      clearInterval(videoProgressRef.current);
    }

    video.muted = true;
    video.loop = false;
    video.currentTime = 1;
    setVideoLoading(true);

    let loadProgress = 0;
    const loadInterval = setInterval(() => {
      loadProgress += 10;
      setVideoProgress(loadProgress);
      if (loadProgress >= 100) {
        clearInterval(loadInterval);
        setVideoLoading(false);
      }
    }, 100);

    setTimeout(() => {
      video.play().then(() => {
        setVideoLoading(false);
        clearInterval(loadInterval);
        
        const handleVideoEnd = () => {
          setTimeout(() => {
            if (video && !video.paused && video.readyState >= 3) {
              video.currentTime = 1;
              video.play().catch(console.log);
            }
          }, 10000);
        };
        
        video.addEventListener('ended', handleVideoEnd);
        
        return () => {
          video.removeEventListener('ended', handleVideoEnd);
        };
      }).catch(console.log);
    }, 1000);

    videoProgressRef.current = setInterval(() => {
      updateVideoProgress(video);
    }, 100);

    const handleVideoClick = () => {
      video.currentTime = 1;
      video.play().catch(console.log);
    };

    video.addEventListener('click', handleVideoClick);

    return () => {
      video.removeEventListener('click', handleVideoClick);
      if (videoIntervalRef.current) {
        clearInterval(videoIntervalRef.current);
      }
      if (videoProgressRef.current) {
        clearInterval(videoProgressRef.current);
      }
      clearInterval(loadInterval);
    };
  }, [updateVideoProgress]);

  // Setup video when media loads
  useEffect(() => {
    if (videoRef.current && currentQuestion?.has_media && currentQuestion?.media_type === 'video') {
      return setupVideoAutoplay(videoRef.current);
    }
  }, [currentQuestion, setupVideoAutoplay]);

  // Setup after-answer video
  useEffect(() => {
    if (afterVideoRef.current && afterAnswerMedia) {
      return setupVideoAutoplay(afterVideoRef.current);
    }
  }, [afterAnswerMedia, setupVideoAutoplay]);

  // Cleanup intervals on unmount
  useEffect(() => {
    return () => {
      if (videoIntervalRef.current) {
        clearInterval(videoIntervalRef.current);
      }
      if (videoProgressRef.current) {
        clearInterval(videoProgressRef.current);
      }
    };
  }, []);

  // Fetch lobby information with 403 error handling
  useEffect(() => {
    const fetchLobbyInfo = async () => {
      try {
        console.log(`Fetching lobby info for ID: ${lobbyId}`);
        setSyncing(true);
        const response = await api.get(`/lobbies/lobbies/${lobbyId}`);
        
        if (response.data.status === "ok") {
          console.log("Lobby info loaded successfully:", response.data.data);
          console.log("Question IDs from server:", response.data.data.question_ids);
          console.log("Question IDs length:", response.data.data.question_ids?.length);
          setLobbyInfo(response.data.data);
          
          if (response.data.data.status === 'completed' || response.data.data.status === 'inactive') {
            setTestCompleted(true);
            fetchTestResults();
            return;
          }
          
          setIsExamMode(response.data.data.exam_mode === true);
          
          // Определяем, является ли текущий пользователь хостом
          if (typeof response.data.data.is_host === 'boolean') {
            setIsHost(response.data.data.is_host);
          } else if (response.data.data.host_id && currentUser?.id === response.data.data.host_id) {
            setIsHost(true);
          }
          
          // Initialize exam timer if in exam mode
          if (response.data.data.exam_mode && response.data.data.exam_timer) {
            const serverTimeLeft = response.data.data.exam_timer.time_left;
            setTimeLeft(serverTimeLeft);
            localStorage.setItem(`exam_timer_${lobbyId}`, serverTimeLeft.toString());
          }
          
          if (response.data.data.question_ids && response.data.data.question_ids.length > 0) {
            console.log("Setting questions array:", response.data.data.question_ids);
            setQuestions(response.data.data.question_ids);
            // Сохраняем questions в localStorage для восстановления при необходимости
            localStorage.setItem(`questions_${lobbyId}`, JSON.stringify(response.data.data.question_ids));
            
            // Получаем ответы пользователя
            const serverAnswers = response.data.data.user_answers || {};
            let localAnswers = {};
            const savedAnswers = localStorage.getItem(`userAnswers_${lobbyId}`);
            if (savedAnswers) {
              try {
                localAnswers = JSON.parse(savedAnswers);
              } catch (e) {
                console.error("Error parsing saved answers:", e);
              }
            }
            
            const mergedAnswers = { ...localAnswers, ...serverAnswers };
            
            if (Object.keys(mergedAnswers).length > 0) {
              setUserAnswers(mergedAnswers);
              localStorage.setItem(`userAnswers_${lobbyId}`, JSON.stringify(mergedAnswers));
              
              // В мультиплеере не изменяем индекс на основе ответов пользователя
              // Индекс управляется только сервером через current_index
              console.log('Восстановлены ответы пользователя:', Object.keys(mergedAnswers).length, 'ответов');
            }
            
            // Синхронизируем текущий индекс вопроса для всех участников
            if (response.data.data.current_index !== undefined) {
              const serverCurrentIndex = response.data.data.current_index;
              console.log(`Синхронизация: сервер показывает индекс ${serverCurrentIndex}, локальный индекс ${currentQuestionIndex}`);
              
              // Всегда синхронизируемся с сервером в мультиплеере
              if (serverCurrentIndex !== currentQuestionIndex) {
                console.log(`Обновляем локальный индекс с ${currentQuestionIndex} на ${serverCurrentIndex}`);
                setCurrentQuestionIndex(serverCurrentIndex);
                localStorage.setItem(`currentQuestionIndex_${lobbyId}`, serverCurrentIndex.toString());
                
                // Сбрасываем состояние вопроса при синхронизации
                setAnswerSubmitted(false);
                setSelectedAnswer(null);
                setCorrectAnswer(null);
                setExplanation(null);
                setAfterAnswerMedia(null);
              }
            }
          }
        } else {
          const errMsg = response.data.message || '';
          if (response.data.status === 403 && errMsg.includes('не являетесь участником')) {
            notify.error(errMsg);
            navigate('/dashboard');
          } else {
            setError(errMsg || 'Failed to load test information');
          }
        }
        
        setLoading(false);
        setSyncing(false);
      } catch (err) {
        console.error('Error fetching lobby info:', err);
        const errMsg = err.response?.data?.message || '';
        if (err.response?.status === 403 && errMsg.includes('не являетесь участником')) {
          notify.error(errMsg);
          navigate('/dashboard');
        } else {
          setError(errMsg || 'Failed to load test information');
        }
        setLoading(false);
        setSyncing(false);
      }
    };

    if (currentUser && lobbyId) {
      fetchLobbyInfo();
    }
  }, [lobbyId, currentUser, navigate]);

  // Save user answers to localStorage
  useEffect(() => {
    if (Object.keys(userAnswers).length > 0) {
      localStorage.setItem(`userAnswers_${lobbyId}`, JSON.stringify(userAnswers));
    }
  }, [userAnswers, lobbyId]);

  // Fetch current question effect
  useEffect(() => {
    if (testCompleted) return;
    
    const isLastQuestion = currentQuestionIndex === questions.length - 1;
    const currentQuestionId = questions[currentQuestionIndex];
    const isQuestionAnswered = userAnswers[currentQuestionId] !== undefined;
    
    if (isLastQuestion && isQuestionAnswered) {
      console.log("Last question is already answered");
      return;
    }
    
    fetchCurrentQuestion().catch(err => {
      if (err.response?.status === 400 && 
          (err.response?.data?.message?.includes("не активен") || 
           err.response?.data?.message?.includes("не запущен"))) {
        console.log("Test status changed to inactive");
        if (isLastQuestion) {
          setError(null);
        }
      } else {
        console.error('Error fetching question:', err);
      }
    });
  }, [lobbyId, questions, currentQuestionIndex, userAnswers, isExamMode, testCompleted, fetchCurrentQuestion]);

  // Check if current user answered current question
  const currentQuestionId = questions[currentQuestionIndex];
  const hasCurrentUserAnswered = userAnswers[currentQuestionId] !== undefined;

  // Automatic periodic sync (host only)
  useEffect(() => {
    if (!isHost || testCompleted) return;

    const interval = setInterval(async () => {
      try {
        await api.post(`/lobbies/lobbies/${lobbyId}/sync-state`);
      } catch (err) {
        console.error('Auto-sync error:', err?.response?.data || err.message);
      }
    }, 15000); // every 15 seconds

    return () => clearInterval(interval);
  }, [isHost, testCompleted, lobbyId]);

  // Loading state
  if (loading) {
    return (
      <div className={`app-container ${isDarkTheme ? 'dark-theme' : ''}`}>
        <DashboardHeader 
          profileData={profileData} 
          toggleSidebar={toggleSidebar} 
          isSidebarOpen={isSidebarOpen} 
          onToggleTheme={handleToggleTheme} 
          onChangeLanguage={handleChangeLanguage}
          currentLanguage={language}
          currentTheme={theme}
        />
        <DashboardSidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
        
        <div className={`main-content ${isSidebarOpen ? 'sidebar-open' : ''}`}>
          <div className="loading-container">
            <div className="loading-bar-container">
              <div className="loading-bar"></div>
            </div>
            <div className="loading-text">{getTranslation('loading')}</div>
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
          onChangeLanguage={handleChangeLanguage}
          currentLanguage={language}
          currentTheme={theme}
        />
        <DashboardSidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
        
        <div className={`main-content ${isSidebarOpen ? 'sidebar-open' : ''}`}>
          <div className="loading-container">
            <FaTimes size={48} style={{ color: 'var(--error)', marginBottom: 'var(--space-lg)' }} />
            <h2 style={{ marginBottom: 'var(--space-md)' }}>{getTranslation('error')}</h2>
            <p style={{ marginBottom: 'var(--space-xl)', textAlign: 'center' }}>{error}</p>
            <button className="btn btn-primary" onClick={handleReturnToDashboard}>
              {getTranslation('returnToDashboard')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Test results (similar to TestPage but with multiplayer results)
  if (testCompleted && testResults) {
    const percentage = testResults.user_result.percentage;
    const correctCount = testResults.user_result.correct_count;
    const totalQuestions = testResults.user_result.total_questions;
    const isPassed = testResults.user_result.passed || percentage >= 70;
    
    return (
      <div className={`app-container ${isDarkTheme ? 'dark-theme' : ''}`}>
        <DashboardHeader 
          profileData={profileData} 
          toggleSidebar={toggleSidebar} 
          isSidebarOpen={isSidebarOpen} 
          onToggleTheme={handleToggleTheme} 
          onChangeLanguage={handleChangeLanguage}
          currentLanguage={language}
          currentTheme={theme}
        />
        <DashboardSidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
        
        <div className={`main-content ${isSidebarOpen ? 'sidebar-open' : ''}`}>
          <div className="test-results-container">
            <div className="results-header">
              <div className={`results-icon ${isPassed ? 'success' : 'failed'}`}>
                {isPassed ? <FaStar size={48} /> : <FaTimes size={48} />}
              </div>
              
              <div className="results-title-section">
                <h1 className="results-title">{getTranslation('multiplayerTestResults') || 'Multiplayer Test Results'}</h1>
                <div className="results-subtitle">{getTranslation('yourPerformance') || 'Your Performance'}</div>
                <div className={`results-status ${isPassed ? 'passed' : 'failed'}`}>
                  {isPassed ? getTranslation('passed') : getTranslation('failed')}
                </div>
              </div>
            </div>
            
            <div className="results-actions">
              <button className="btn btn-primary" onClick={handleReturnToDashboard}>
                <FaStar />
                {getTranslation('returnToDashboard')}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Active test - similar structure to TestPage
  return (
    <div className={`app-container ${isDarkTheme ? 'dark-theme' : ''}`}>
      <DashboardHeader 
        profileData={profileData} 
        toggleSidebar={toggleSidebar} 
        isSidebarOpen={isSidebarOpen} 
        onToggleTheme={handleToggleTheme} 
        onChangeLanguage={handleChangeLanguage}
        currentLanguage={language}
        currentTheme={theme}
      />
      <DashboardSidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
      
      {/* Sync indicator */}
      {syncing && (
        <div className="sync-indicator">
          <div className="sync-spinner"></div>
          <span>{getTranslation('syncingWithServer')}</span>
        </div>
      )}
      
      {/* Question Navigation Overlay */}
      <div 
        className={`question-nav-overlay ${isQuestionNavOpen ? 'open' : ''}`}
        onClick={closeQuestionNav}
      />
      
      <div className={`main-content ${isSidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="test-page">
          {/* Test Header */}
          <div className="test-header">
            <div className="test-progress">
              <div className="progress-text">
                <FaUsers />
                <span className="multiplayer-indicator">{getTranslation('multiplayer') || 'Multiplayer'}</span>
                {getTranslation('question')} {currentQuestionIndex + 1} {getTranslation('of')} {questions.length}
              </div>
              <div className="progress-bar">
                <div 
                  className="progress" 
                  style={{ width: `${((currentQuestionIndex + 1) / questions.length) * 100}%` }}
                ></div>
              </div>
            </div>
            
            <div className="header-controls">
              {isExamMode && (
                <div className={`test-timer ${timeLeft < 300 ? 'timer-warning' : ''}`}>
                  <FaClock />
                  <span>{formatTime(timeLeft)}</span>
                </div>
              )}
              
              <div className="connection-status">
                <div className={`connection-dot ${connectionStatus === 'connected' ? 'online' : connectionStatus === 'error' ? 'offline' : 'reconnecting'}`}></div>
                <span>{connectionStatus === 'connected' ? getTranslation('online') : connectionStatus === 'error' ? getTranslation('offline') : getTranslation('connecting')}</span>
              </div>
              
              <div className="participants-count">
                <FaUsers />
                <span className="participants-count-number">{validParticipants.length}</span>
                <span>{getTranslation('participants')}</span>
              </div>
            </div>
          </div>
          
          {/* Test Content */}
          <div className="test-content">
            {/* Main Question Content */}
            <div className="question-main">
              {currentQuestion && (
                <>
                  <div className="question-header">
                    <div className="question-title">
                      {localizeText(currentQuestion.question_text)}
                    </div>
                  </div>
                  
                  {/* Media Section */}
                  {mediaLoading ? (
                    <div className="loading-container" style={{ height: '200px' }}>
                      <div className="loading-bar-container">
                        <div className="loading-bar"></div>
                      </div>
                      <div className="loading-text">{getTranslation('loadingMedia')}</div>
                    </div>
                  ) : (
                    <div className="question-media">
                      {answerSubmitted && !isExamMode && afterAnswerMedia ? (
                        currentQuestion.after_answer_media_type === 'video' ? (
                          <div className="media-container">
                            <div className="video-container">
                              <video 
                                ref={afterVideoRef}
                                className="question-video"
                                src={afterAnswerMedia}
                                onError={() => setVideoError(true)}
                                preload="metadata"
                                playsInline
                                muted
                                loop
                              />
                            </div>
                          </div>
                        ) : (
                          <img 
                            src={afterAnswerMedia}
                            alt="Explanation"
                            className="question-image"
                            onError={(e) => {
                              console.log('After-answer image failed to load:', afterAnswerMedia);
                              e.target.style.display = 'none';
                              // Показываем заглушку NO IMAGE
                              const placeholder = e.target.parentElement.querySelector('.no-media-placeholder');
                              if (!placeholder) {
                                const noMediaDiv = document.createElement('div');
                                noMediaDiv.className = 'no-media-placeholder';
                                noMediaDiv.innerHTML = `
                                  <div style="display: flex; align-items: center; justify-content: center; font-size: 16px; color: #666;">
                                    <span style="margin-right: 8px;">📷</span>
                                    NO IMAGE
                                  </div>
                                `;
                                e.target.parentElement.appendChild(noMediaDiv);
                              }
                            }}
                          />
                        )
                      ) : (
                        currentQuestion.has_media && currentQuestion.media_url ? (
                          currentQuestion.media_type === 'video' ? (
                            videoError ? (
                              <div className="no-media-placeholder">
                                <FaExclamationTriangle style={{ marginRight: 'var(--space-sm)' }} />
                                {getTranslation('videoError')}
                              </div>
                            ) : (
                              <div className="media-container">
                                <div className="video-container">
                                  <video 
                                    ref={videoRef}
                                    className="question-video"
                                    src={currentQuestion.media_url}
                                    onError={() => setVideoError(true)}
                                    preload="metadata"
                                    playsInline
                                    muted
                                    loop
                                  />
                                </div>
                              </div>
                            )
                          ) : (
                            <img 
                              src={currentQuestion.media_url}
                              alt="Question"
                              className="question-image"
                              onError={(e) => {
                                console.log('Image failed to load:', currentQuestion.media_url);
                                e.target.style.display = 'none';
                                // Показываем заглушку NO IMAGE
                                const placeholder = e.target.parentElement.querySelector('.no-media-placeholder');
                                if (!placeholder) {
                                  const noMediaDiv = document.createElement('div');
                                  noMediaDiv.className = 'no-media-placeholder';
                                  noMediaDiv.innerHTML = `
                                    <div style="display: flex; align-items: center; justify-content: center; font-size: 16px; color: #666;">
                                      <span style="margin-right: 8px;">📷</span>
                                      NO IMAGE
                                    </div>
                                  `;
                                  e.target.parentElement.appendChild(noMediaDiv);
                                }
                              }}
                            />
                          )
                        ) : currentQuestion.has_media ? (
                          <div className="no-media-placeholder">
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '16px', color: '#666' }}>
                              <span style={{ marginRight: '8px' }}>📷</span>
                              NO IMAGE
                            </div>
                          </div>
                        ) : (
                          <div className="no-media-placeholder">
                            <FaQuestionCircle style={{ marginRight: 'var(--space-sm)' }} />
                            {getTranslation('noMedia')}
                          </div>
                        )
                      )}
                    </div>
                  )}
                  
                  {/* Answer Options */}
                  <div className="answer-options">
                    {currentQuestion.answers && currentQuestion.answers.map((answer, index) => {
                      const answerText = localizeText(answer);
                      
                      let answerClass = "answer-option";
                      if (answerSubmitted) {
                        if (isExamMode) {
                          if (index === selectedAnswer) {
                            answerClass += " selected";
                          }
                        } else {
                          // В мультиплеере показываем правильный ответ только если он был показан хостом
                          if (correctAnswer !== null) {
                            if (index === selectedAnswer && index === correctAnswer) {
                              answerClass += " correct";
                            } else if (index === selectedAnswer && index !== correctAnswer) {
                              answerClass += " incorrect";
                            } else if (index === correctAnswer) {
                              answerClass += " correct";
                            }
                          } else {
                            // Если правильный ответ еще не показан, показываем только выбранный ответ
                            if (index === selectedAnswer) {
                              answerClass += " selected";
                            }
                          }
                        }
                      } else if (index === selectedAnswer) {
                        answerClass += " selected";
                      }
                      
                      return (
                        <div 
                          key={index} 
                          className={answerClass}
                          onClick={() => {
                            // Проверяем, может ли пользователь отвечать
                            if (answerSubmitted) {
                              console.log('User already answered this question');
                              return;
                            }
                            
                            // Если хост уже показал правильный ответ, больше нельзя отвечать
                            if (correctAnswer !== null && !isExamMode) {
                              console.log('Cannot answer: correct answer already shown by host');
                              return;
                            }
                            
                            handleAnswerSubmit(index);
                          }}
                          tabIndex={answerSubmitted || (correctAnswer !== null && !isExamMode) ? -1 : 0}
                          onKeyPress={(e) => {
                            if (e.key === 'Enter' && !answerSubmitted && !(correctAnswer !== null && !isExamMode)) {
                              handleAnswerSubmit(index);
                            }
                          }}
                        >
                          <div className="answer-label">{String.fromCharCode(65 + index)}</div>
                          <div className="answer-text">{answerText}</div>
                        </div>
                      );
                    })}
                  </div>
                  
                  {/* Answer Status for Multiplayer */}
                  {!isExamMode && (
                    <div className="answer-status-section">
                      {answerSubmitted ? (
                        // Пользователь ответил
                        correctAnswer !== null ? (
                          <div className={`answer-status ${selectedAnswer === correctAnswer ? 'correct' : 'incorrect'}`}>
                            {selectedAnswer === correctAnswer ? (
                              <>
                                <FaCheck />
                                <span>Правильно! Вы выбрали верный ответ.</span>
                              </>
                            ) : (
                              <>
                                <FaTimes />
                                <span>Неправильно. Правильный ответ: {String.fromCharCode(65 + correctAnswer)}</span>
                              </>
                            )}
                          </div>
                        ) : (
                          <div className="answer-status waiting">
                            <FaClock />
                            <span>Ответ отправлен. Ожидание показа правильного ответа хостом...</span>
                          </div>
                        )
                      ) : (
                        // Пользователь НЕ ответил
                        correctAnswer !== null ? (
                          <div className="answer-status missed">
                            <FaExclamationTriangle />
                            <span>Вы не успели ответить. Правильный ответ: {String.fromCharCode(65 + correctAnswer)}</span>
                          </div>
                        ) : null
                      )}
                    </div>
                  )}
                  
                  {/* Explanation */}
                  {answerSubmitted && !isExamMode && explanation && (
                    <div className="answer-explanation">
                      <div className="explanation-header">
                        <FaLightbulb />
                        <div className="explanation-title">{getTranslation('explanation')}</div>
                      </div>
                      <div className="explanation-content">
                        {localizeText(explanation)}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
          
          {/* Navigation section intentionally left empty in multiplayer mode */}
          <div className="test-navigation" />
          
          {/* Bottom Panel for Participants */}
          <div className="bottom-panel">
            {/* Participants Section */}
            <div className="participants-section">
              <div className="participants-header">
                <h3>
                  <FaUsers />
                  {getTranslation('participants')} ({validParticipants.length})
                </h3>
                <div className="connection-status">
                  <div className={`connection-dot ${connectionStatus === 'connected' ? 'online' : 'offline'}`}></div>
                  <span>{connectionStatus === 'connected' ? getTranslation('connected') : getTranslation('disconnected')}</span>
                </div>
              </div>
              
              <div className="participants-grid">
                {validParticipants && validParticipants.length > 0 ? 
                  validParticipants.map((participant, index) => renderParticipantCard(participant, index)).filter(Boolean) :
                  <div className="no-participants">
                    <span>{getTranslation('noParticipants') || 'No participants'}</span>
                  </div>
                }
              </div>
            </div>
            
            {/* Host Controls */}
            {isHost && (
              <div className="host-controls-section">
                <div className="host-controls-header">
                  <h3>
                    <FaCrown />
                    {getTranslation('hostControls') || 'Host Controls'}
                  </h3>
                </div>
                
                <div className="host-controls-grid">
                  <button 
                    className="control-btn primary"
                    onClick={handleHostNextQuestion}
                    disabled={syncing}
                  >
                    <FaArrowRight />
                    {getTranslation('nextQuestion')}
                  </button>
                  
                  <button 
                    className="control-btn secondary"
                    onClick={handleShowCorrectAnswer}
                    disabled={syncing}
                  >
                    <FaLightbulb />
                    {getTranslation('showAnswer') || 'Show Answer'}
                  </button>
                  
                  <button 
                    className="control-btn danger"
                    onClick={handleHostFinishTest}
                    disabled={syncing}
                  >
                    <FaFlag />
                    {getTranslation('finishTest')}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MultiplayerTestPage; 