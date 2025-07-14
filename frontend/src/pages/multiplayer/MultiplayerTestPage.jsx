import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useLanguage } from '../../contexts/LanguageContext';
import { useTheme } from '../../contexts/ThemeContext';
import { translations } from '../../translations/translations';
import api from '../../utils/axios';
import { notify } from '../../components/notifications/NotificationSystem';
import { localizeText } from '../../utils/languageUtil';
import LobbyHeader from '../../components/lobby/LobbyHeader';
import useMultiplayerSocket from '../../hooks/useMultiplayerSocket';
import { 
  FaTimes, 
  FaCheck, 
  FaArrowLeft, 
  FaArrowRight, 
  FaFlag, 
  FaLanguage, 
  FaMoon, 
  FaSun, 
  FaHistory, 
  FaExclamationTriangle,
  FaPlay, 
  FaPause, 
  FaVolumeUp, 
  FaVolumeMute, 
  FaExpand,
  FaBars, 
  FaQuestionCircle, 
  FaLightbulb, 
  FaClock, 
  FaStar, 
  FaChartBar, 
  FaUser,
  FaWifi,
  FaSignOutAlt,
  FaEye,
  FaEyeSlash,
  FaCrown,
  FaGraduationCap,
  FaUserTimes,
  FaUsers,
  FaCog,
  FaChevronRight,
  FaChevronLeft,
  FaTruck,
  FaTruckMoving,
  FaBusAlt
} from 'react-icons/fa';
import { 
  MdDirectionsBike, 
  MdDirectionsCar, 
  MdLocalShipping, 
  MdTimer 
} from 'react-icons/md';
import './MultiplayerTestPage.css';

const useMediaLoader = (url) => {
  const cacheRef = useRef({});
  const [media, setMedia] = useState({ src: null, isLoading: true, error: null });

  useEffect(() => {
    if (!url) {
      setMedia({ src: null, isLoading: false, error: null });
      return;
    }

    let isCancelled = false;

    const loadMedia = async () => {
      if (cacheRef.current[url]) {
        setMedia({ src: cacheRef.current[url], isLoading: false, error: null });
        return;
      }

      setMedia({ src: null, isLoading: true, error: null });

      try {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Failed to fetch media: ${response.statusText}`);
        }
        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);
        
        if (!isCancelled) {
          cacheRef.current[url] = blobUrl;
          setMedia({ src: blobUrl, isLoading: false, error: null });
        }
      } catch (error) {
        if (!isCancelled) {
          setMedia({ src: null, isLoading: false, error: error.message });
        }
      }
    };

    loadMedia();

    return () => {
      isCancelled = true;
    };
  }, [url]);

  useEffect(() => {
    const cache = cacheRef.current;
    return () => {
      Object.values(cache).forEach(URL.revokeObjectURL);
    };
  }, []);

  return media;
};

const QuestionMedia = React.memo(({
  currentQuestion,
  answerSubmitted,
  afterAnswerMedia,
  afterAnswerMediaType,
  videoRef,
  afterVideoRef,
  getTranslation
}) => {
  const mediaUrl = answerSubmitted && afterAnswerMedia 
    ? afterAnswerMedia 
    : currentQuestion?.media_url;

  const mediaType = answerSubmitted && afterAnswerMedia
    ? afterAnswerMediaType
    : currentQuestion?.media_type;

  const { src: loadedSrc, isLoading, error } = useMediaLoader(mediaUrl);
  const activeVideoRef = answerSubmitted ? afterVideoRef : videoRef;

  useEffect(() => {
    if (mediaType === 'video' && loadedSrc && activeVideoRef.current) {
      const videoElement = activeVideoRef.current;
      
      const playVideo = () => {
        if (videoElement) {
          videoElement.currentTime = 0;
          videoElement.play().catch(e => console.error("Video play failed:", e));
        }
      };

      playVideo(); 

      const intervalId = setInterval(playVideo, 10000);

      return () => clearInterval(intervalId);
    }
  }, [loadedSrc, mediaType, activeVideoRef]);

  const handleVideoClick = () => {
    if (activeVideoRef.current) {
      activeVideoRef.current.currentTime = 0;
      activeVideoRef.current.play().catch(e => console.error("Video play failed on click:", e));
    }
  };

  if (isLoading) {
    return (
      <div className="loading-container" style={{ height: '100%', width: '100%' }}>
        <div className="loading-bar-container"><div className="loading-bar"></div></div>
        <div className="loading-text">{getTranslation('loadingMedia')}</div>
      </div>
    );
  }

  if (error || !loadedSrc) {
    return (
      <video 
        className="fallback-video" 
        src="/static/no_image.MP4" 
        preload="metadata" 
        playsInline 
        muted 
        loop 
        autoPlay 
      />
    );
  }

  if (mediaType === 'video') {
    return (
      <video
        ref={answerSubmitted ? afterVideoRef : videoRef}
        key={loadedSrc}
        className="question-video"
        src={loadedSrc}
        preload="metadata"
        playsInline
        muted
        onClick={handleVideoClick}
      />
    );
  } else {
    return (
      <img 
        src={loadedSrc} 
        key={loadedSrc} 
        alt="Question Media" 
        className="question-image" 
      />
    );
  }
});

const MultiplayerTestPage = () => {
  const { lobbyId } = useParams();
  const navigate = useNavigate();
  const { language } = useLanguage();
  const t = translations[language] || translations['ru'];
  const { isDark } = useTheme();
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [answerSubmitted, setAnswerSubmitted] = useState(false);
  const [correctAnswer, setCorrectAnswer] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const [afterAnswerMedia, setAfterAnswerMedia] = useState(null);
  const [afterAnswerMediaType, setAfterAnswerMediaType] = useState('image');
  const [lobbyInfo, setLobbyInfo] = useState(null);
  const [mediaLoading, setMediaLoading] = useState(false);
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
  const [answerDetailsCache, setAnswerDetailsCache] = useState({});
  
  // Multiplayer specific states
  const [participants, setParticipants] = useState([]);
  const [isHost, setIsHost] = useState(false);
  const [showAnswers, setShowAnswers] = useState(false);
  const [participantAnswers, setParticipantAnswers] = useState({});
  const [myAnswers, setMyAnswers] = useState({});
  const [currentUserId, setCurrentUserId] = useState(null);
  const [isGuest, setIsGuest] = useState(() => localStorage.getItem('isGuest') === 'true');
  const [modalMessage, setModalMessage] = useState(null);
  
  const intervalRef = useRef(null);
  const videoRef = useRef(null);
  const afterVideoRef = useRef(null);

  // Helper: show error both in UI and notification system
  const showError = useCallback((msg) => {
    setError(msg);
    notify.error(msg, { important: true });
  }, []);

  // Fetch correct answer and participant answers
  const fetchCorrectAnswer = useCallback(async (questionId) => {
    if (answerDetailsCache[questionId]) {
      const cachedData = answerDetailsCache[questionId];
      setCorrectAnswer(cachedData.correctAnswer);
      setExplanation(cachedData.explanation);
      setParticipantAnswers(cachedData.participantAnswers);
      if (cachedData.afterAnswerMedia) {
        setAfterAnswerMedia(cachedData.afterAnswerMedia);
        setAfterAnswerMediaType(cachedData.afterAnswerMediaType);
      }
      return;
    }

    try {
      console.log(`Fetching correct answer for question ${questionId}`);
      const response = await api.get(`/multiplayer/lobbies/${lobbyId}/current-answers`);
      
      if (response.data.status === "ok") {
        const correctData = response.data.data;
        console.log('Correct answer data received:', correctData);
        
        const newCorrectAnswer = {
          index: correctData.correct_answer_index,
          hasAfterAnswerMedia: correctData.has_after_answer_media
        };
        setCorrectAnswer(newCorrectAnswer);
        
        const newExplanation = correctData.explanation && Object.keys(correctData.explanation).length > 0 ? correctData.explanation : null;
        setExplanation(newExplanation);

        // Set participant answers
        setParticipantAnswers(correctData.participants_raw_answers || {});

        let newAfterAnswerMedia = null;
        let newAfterAnswerMediaType = 'image';
        
        // Fetch after-answer media if available
        if (correctData.has_after_answer_media) {
          console.log('Fetching after-answer media...', correctData.has_after_answer_media, correctData.after_answer_media_filename, correctData.after_answer_media_file_id, correctData.after_answer_media_id);
          try {
            // В мультиплеерном режиме используем правильный эндпоинт
            newAfterAnswerMedia = `/api/multiplayer/lobbies/${lobbyId}/after-answer-media/${questionId}`;
            
            // Проверяем тип медиа по имени файла
            if (correctData.after_answer_media_filename) {
              const filename = correctData.after_answer_media_filename.toLowerCase();
              if (filename.endsWith('.mp4') || filename.endsWith('.webm') || filename.endsWith('.mov')) {
                newAfterAnswerMediaType = 'video';
              } else {
                newAfterAnswerMediaType = 'image';
              }
            }
            
            setAfterAnswerMedia(newAfterAnswerMedia);
            setAfterAnswerMediaType(newAfterAnswerMediaType);
            console.log('After-answer media loaded successfully:', newAfterAnswerMedia, newAfterAnswerMediaType);
          } catch (err) {
            console.error('Error fetching after-answer media:', err);
            setAfterAnswerMedia(null);
            setAfterAnswerMediaType('image');
          }
        } else {
          console.log('No after-answer media available for this question');
          setAfterAnswerMedia(null);
          setAfterAnswerMediaType('image');
        }
        
        // Update cache
        setAnswerDetailsCache(prevCache => ({
            ...prevCache,
            [questionId]: {
                correctAnswer: newCorrectAnswer,
                explanation: newExplanation,
                participantAnswers: correctData.participants_raw_answers || {},
                afterAnswerMedia: newAfterAnswerMedia,
                afterAnswerMediaType: newAfterAnswerMediaType,
            }
        }));
      }
    } catch (err) {
      console.error('Error fetching correct answer:', err);
    }
  }, [lobbyId, answerDetailsCache]);

  // Get current user ID from API
  const getCurrentUserId = useCallback(async () => {
      try {
        const response = await api.get('/users/me');
      if (response.data.status === 'ok' && response.data.data) {
        return response.data.data.id || response.data.data._id;
      }
    } catch (error) {
      console.error('Error getting current user ID:', error);
    }
    return null;
  }, []);

  // 1. Функция для получения списка участников по HTTP
  const fetchParticipants = useCallback(async () => {
    if (!lobbyId) return;
    try {
      const response = await api.get(`/multiplayer/lobbies/${lobbyId}/participants`);
      if (response.data.status === 'ok') {
        setParticipants(response.data.data.participants || []);
      }
    } catch (error) {
      console.error('Failed to fetch participants:', error);
      setError(t['failedToLoadParticipants'] || 'Не удалось загрузить участников');
    }
  }, [lobbyId, t]);

  // Fetch current question - перемещаем выше
  const fetchCurrentQuestion = useCallback(async () => {
    if (!lobbyId) return;
    
    try {
      setMediaLoading(true);
      setVideoError(false);
      
      console.log(`Fetching current question for lobby ${lobbyId}`);
      
      const response = await api.get(`/multiplayer/lobbies/${lobbyId}/current-question`);
      
      if (response.data.status === "ok") {
        const questionData = response.data.data;
        
        console.log('Current question loaded:', questionData);
        console.log('After answer media info:', {
          has_after_answer_media: questionData.has_after_answer_media,
          after_answer_media_filename: questionData.after_answer_media_filename,
          after_answer_media_file_id: questionData.after_answer_media_file_id,
          after_answer_media_id: questionData.after_answer_media_id
        });
        
        // Set media URL if question has media
        if (questionData.has_media && questionData.media_filename) {
          const mediaUrl = `/api/multiplayer/lobbies/${lobbyId}/media/${questionData._id}`;
          questionData.media_url = mediaUrl;
          
          // Determine media type
            const filename = questionData.media_filename.toLowerCase();
            if (filename.endsWith('.mp4') || filename.endsWith('.webm') || filename.endsWith('.mov')) {
              questionData.media_type = 'video';
            } else {
              questionData.media_type = 'image';
            }
          } else {
          // Set default values if no media
          questionData.media_url = null;
          questionData.media_type = null;
        }
        
        setCurrentQuestion(questionData);
        setAnswerSubmitted(false);
        setSelectedAnswer(null);
        setCorrectAnswer(null);
        setExplanation(null);
        setAfterAnswerMedia(null);
        setAfterAnswerMediaType('image');
        
        // Update show_answers state from question data
        setShowAnswers(questionData.show_answers || false);
        
        // Check if user already answered this question
        if (questionData.user_answer_index !== null && questionData.user_answer_index !== undefined) {
          setSelectedAnswer(questionData.user_answer_index);
          setAnswerSubmitted(true);
        }
        
        // If show_answers is true, fetch correct answer and participant answers immediately
        if (questionData.show_answers) {
          console.log('Question has show_answers=true, fetching correct answer...');
          // Небольшая задержка для обеспечения правильного порядка загрузки
          setTimeout(() => {
            fetchCorrectAnswer(questionData._id);
          }, 200);
        }
        
        setMediaLoading(false);
      } else {
        console.error('Failed to load question:', response.data.message);
        showError(response.data.message || 'Failed to load question');
        setMediaLoading(false);
      }
    } catch (err) {
      console.error('Error fetching current question:', err);
        showError(err.response?.data?.message || 'Failed to load question');
      setMediaLoading(false);
    }
  }, [lobbyId, fetchCorrectAnswer, showError]);

  // 2. Колбэки для сокета - стабилизируем их с помощью useRef
  const socketCallbacksRef = useRef({
    handleUserEvent: (event) => {
      console.log(`Socket event received: ${event}, fetching participants...`);
      fetchParticipants();
    },
    handleSocketError: (errorMessage) => {
      console.error('WebSocket error:', errorMessage);
      // Не показываем ошибку пользователю, если это временная проблема соединения
      if (errorMessage.includes('503') || errorMessage.includes('Service Unavailable')) {
        console.log('WebSocket service temporarily unavailable, will retry...');
      } else {
        setError(errorMessage);
      }
    },
    handleKicked: (reason) => {
      setModalMessage({
        title: 'Вы были исключены',
        message: reason,
        buttonText: 'Вернуться на главную',
        redirectPath: isGuest ? '/' : '/dashboard'
      });
    },
    handleLobbyClosed: (reason) => {
      setModalMessage({
        title: 'Лобби закрыто',
        message: reason,
        buttonText: 'Вернуться в дашборд',
        redirectPath: isGuest ? '/' : '/dashboard'
      });
    },
    handleTestFinished: (data) => {
      console.log('Test finished event received:', data);
      setTestCompleted(true);
      navigate(`/multiplayer/results/${lobbyId}`);
    },
    handleParticipantAnswered: (data) => {
      console.log('Participant answered event received:', data);
      // Refresh participants list to show updated answer status
      fetchParticipants();
      
      // If we're the host and this is not our own answer, we should receive detailed info
      if (isHost && data.user_id !== currentUserId) {
        console.log('Host received participant answer notification, waiting for details...');
      }
    },
    handleParticipantAnswerDetails: (data) => {
      console.log('Participant answer details received:', data);
      
      // Update participant answers with the specific answer
      setParticipantAnswers(prev => ({
        ...prev,
        [data.user_id]: data.answer_index
      }));
      
      // If this is a host's answer, also update for all participants
      if (data.is_host) {
        console.log('Host answered, updating for all participants');
      }
      
      // Refresh participants list to show updated answer status
      fetchParticipants();
    },
    handleCorrectAnswerShown: (data) => {
      console.log('Correct answer shown event received:', data);
      setShowAnswers(true);
      
      // Всегда пытаемся получить правильный ответ, даже если currentQuestion еще не загружен
      if (currentQuestion) {
        console.log('Fetching correct answer after show answers event');
        setTimeout(() => {
          fetchCorrectAnswer(currentQuestion._id);
        }, 500);
      } else {
        // Если currentQuestion еще не загружен, попробуем получить его и затем правильный ответ
        console.log('Current question not loaded yet, fetching it first...');
        setTimeout(() => {
          fetchCurrentQuestion().then(() => {
            // После загрузки вопроса попробуем получить правильный ответ
            setTimeout(() => {
              if (currentQuestion) {
                fetchCorrectAnswer(currentQuestion._id);
              }
            }, 1000);
          });
        }, 500);
      }
    },
    handleNextQuestionEvent: (data) => {
      console.log('Next question event received:', data);
      
      // Reset states for new question
      setShowAnswers(false);
      setAnswerSubmitted(false);
      setSelectedAnswer(null);
      setCorrectAnswer(null);
      setExplanation(null);
      setAfterAnswerMedia(null);
      setAfterAnswerMediaType('image');
      setParticipantAnswers({});
      
      // Update question index
      setCurrentQuestionIndex(data.question_index);
      
      // Fetch new question
      fetchCurrentQuestion();
    }
  });

  // Обновляем колбэки в ref при изменении зависимостей - убираем нестабильные зависимости
  useEffect(() => {
    socketCallbacksRef.current.handleUserEvent = (event) => {
      console.log(`Socket event received: ${event}, fetching participants...`);
      fetchParticipants();
    };
  }, []); // Убираем fetchParticipants из зависимостей

  useEffect(() => {
    socketCallbacksRef.current.handleSocketError = (errorMessage) => {
      console.error('WebSocket error:', errorMessage);
      if (errorMessage.includes('503') || errorMessage.includes('Service Unavailable')) {
        console.log('WebSocket service temporarily unavailable, will retry...');
      } else {
        setError(errorMessage);
      }
    };
  }, []); // Убираем setError из зависимостей

  useEffect(() => {
    socketCallbacksRef.current.handleKicked = (reason) => {
      setModalMessage({
        title: 'Вы были исключены',
        message: reason,
        buttonText: 'Вернуться на главную',
        redirectPath: isGuest ? '/' : '/dashboard'
      });
    };
  }, [isGuest]);

  useEffect(() => {
    socketCallbacksRef.current.handleLobbyClosed = (reason) => {
      setModalMessage({
        title: 'Лобби закрыто',
        message: reason,
        buttonText: 'Вернуться в дашборд',
        redirectPath: isGuest ? '/' : '/dashboard'
      });
    };
  }, [isGuest]);

  useEffect(() => {
    socketCallbacksRef.current.handleTestFinished = (data) => {
      console.log('Test finished event received:', data);
      setTestCompleted(true);
      navigate(`/multiplayer/results/${lobbyId}`);
    };
  }, [navigate, lobbyId]);

  useEffect(() => {
    socketCallbacksRef.current.handleParticipantAnswered = (data) => {
      console.log('Participant answered event received:', data);
      fetchParticipants();
      
      if (isHost && data.user_id !== currentUserId) {
        console.log('Host received participant answer notification, waiting for details...');
      }
    };
  }, [isHost, currentUserId]); // Убираем fetchParticipants из зависимостей

  useEffect(() => {
    socketCallbacksRef.current.handleParticipantAnswerDetails = (data) => {
      console.log('Participant answer details received:', data);
      
      setParticipantAnswers(prev => ({
        ...prev,
        [data.user_id]: data.answer_index
      }));
      
      if (data.is_host) {
        console.log('Host answered, updating for all participants');
      }
      
      fetchParticipants();
    };
  }, []); // Убираем fetchParticipants из зависимостей

  useEffect(() => {
    socketCallbacksRef.current.handleCorrectAnswerShown = (data) => {
      console.log('Correct answer shown event received:', data);
      setShowAnswers(true);
      
      // Всегда пытаемся получить правильный ответ, даже если currentQuestion еще не загружен
      if (currentQuestion) {
        console.log('Fetching correct answer after show answers event');
        setTimeout(() => {
          fetchCorrectAnswer(currentQuestion._id);
        }, 500);
      } else {
        // Если currentQuestion еще не загружен, попробуем получить его и затем правильный ответ
        console.log('Current question not loaded yet, fetching it first...');
        setTimeout(() => {
          fetchCurrentQuestion().then(() => {
            // После загрузки вопроса попробуем получить правильный ответ
            setTimeout(() => {
              if (currentQuestion) {
                fetchCorrectAnswer(currentQuestion._id);
              }
            }, 1000);
          });
        }, 500);
      }
    };
  }, [currentQuestion]); // Убираем fetchCorrectAnswer из зависимостей

  useEffect(() => {
    socketCallbacksRef.current.handleNextQuestionEvent = (data) => {
      console.log('Next question event received:', data);
      
      setShowAnswers(false);
      setAnswerSubmitted(false);
      setSelectedAnswer(null);
      setCorrectAnswer(null);
      setExplanation(null);
      setAfterAnswerMedia(null);
      setAfterAnswerMediaType('image');
      setParticipantAnswers({});
      
      setCurrentQuestionIndex(data.question_index);
      fetchCurrentQuestion();
    };
  }, []); // Убираем fetchCurrentQuestion из зависимостей

  // 3. Инициализация сокета
  const { 
    isConnected: wsConnected, 
    onlineUsers, 
    sendEvent: sendSocketEvent,
    disconnect: disconnectSocket 
  } = useMultiplayerSocket(
    lobbyId, 
    socketCallbacksRef.current.handleUserEvent, 
    socketCallbacksRef.current.handleSocketError,
    socketCallbacksRef.current.handleKicked,
    socketCallbacksRef.current.handleLobbyClosed,
    null, // onLobbyStarted - не нужен для тестовой страницы
    socketCallbacksRef.current.handleParticipantAnswered,
    socketCallbacksRef.current.handleCorrectAnswerShown,
    socketCallbacksRef.current.handleNextQuestionEvent,
    socketCallbacksRef.current.handleTestFinished, // onTestFinished - для завершения теста
    socketCallbacksRef.current.handleParticipantAnswerDetails // onParticipantAnswerDetails - для хоста
  );

  // Load profile data
  useEffect(() => {
    const fetchProfileData = async () => {
      try {
        const response = await api.get('/users/me');
        if (response.data.status === "ok") {
          setProfileData(response.data.data);
          setCurrentUserId(response.data.data.id || response.data.data._id);
      }
    } catch (err) {
        console.error('Error fetching profile data:', err);
      }
    };

    fetchProfileData().catch(() => {
      console.log("Profile data fetch failed silently");
    });
  }, []);

  // Первоначальная загрузка данных о лобби и участниках
  useEffect(() => {
    const initialize = async () => {
      setLoading(true);
      try {
        const [lobbyResponse] = await Promise.all([
          api.get(`/multiplayer/lobbies/${lobbyId}`),
          fetchParticipants()
        ]);
        
        if (lobbyResponse.data.status === 'ok') {
          const lobbyData = lobbyResponse.data.data;
          setLobbyInfo(lobbyData);
          setIsHost(lobbyData.is_host === true);
          setShowAnswers(lobbyData.show_answers === true);
          setTotalQuestions(lobbyData.questions_count || 0);
          setCurrentQuestionIndex(lobbyData.current_index || 0);
          
          // Проверяем статус лобби
          if (lobbyData.status === 'finished') {
            // Лобби завершено - показываем уведомление и перенаправляем
            notify.finish('Лобби завершено! Вы будете перенаправлены.', { 
              important: true,
              duration: 3000 
            });
            
            // Разрываем соединение с сокетом
            disconnectSocket();
            
            // Удаляем токены из localStorage
            localStorage.removeItem('token');
            localStorage.removeItem('isGuest');
            localStorage.removeItem('ws_token');
            delete api.defaults.headers.common['Authorization'];
            
            // Перенаправляем пользователей через 3 секунды
            setTimeout(() => {
              if (isGuest) {
                navigate('/', { replace: true });
              } else {
                navigate('/dashboard', { replace: true });
              }
            }, 3000);
            return;
          }
          
          // Загружаем текущий вопрос только если лобби не завершено
          console.log('Lobby initialized, fetching current question...');
          fetchCurrentQuestion();
        } else {
          setError(lobbyResponse.data.message || t['failedToLoadLobby']);
        }
      } catch (error) {
        setError(error.response?.data?.message || t['failedToLoadLobby']);
    } finally {
        setLoading(false);
      }
    };
    if (lobbyId) {
      initialize();
    }
  }, [lobbyId, fetchParticipants, t, disconnectSocket, navigate, isGuest]); // Убираем fetchCurrentQuestion из зависимостей

  // Handle answer submission
  const handleAnswerSubmit = async (answerIndex) => {
    if (answerSubmitted || !currentQuestion) return;
    
    setSelectedAnswer(answerIndex);
    setAnswerSubmitted(true);
    setSyncing(true);
    
    try {
      const response = await api.post(`/multiplayer/lobbies/${lobbyId}/answer`, {
        question_id: currentQuestion._id,
        answer_index: answerIndex
      });
      
      if (response.data.status === "ok") {
        console.log('Answer submitted successfully');
        
        // Update my answers
        const updatedAnswers = { ...myAnswers, [currentQuestion._id]: answerIndex };
        setMyAnswers(updatedAnswers);
        
        // If answers are shown, fetch correct answer and participant answers
        if (showAnswers) {
          fetchCorrectAnswer(currentQuestion._id);
        }
        
        // Send detailed answer info to host via socket
        if (isHost) {
          // Host sends detailed info to all participants
          sendSocketEvent('participant_answer_details', {
            lobby_id: lobbyId,
            question_id: currentQuestion._id,
            user_id: currentUserId,
            answer_index: answerIndex,
            is_host: true
          });
          
          // Also send general notification to all participants
          sendSocketEvent('participant_answered', {
            lobby_id: lobbyId,
            question_id: currentQuestion._id,
            user_id: currentUserId,
            answer_index: answerIndex
          });
        } else {
          // Regular participants send detailed info to host only
          sendSocketEvent('participant_answer_details', {
            lobby_id: lobbyId,
            question_id: currentQuestion._id,
            user_id: currentUserId,
            answer_index: answerIndex,
            is_host: false
          });
          
          // Also send general notification to all participants
          sendSocketEvent('participant_answered', {
            lobby_id: lobbyId,
            question_id: currentQuestion._id,
            user_id: currentUserId,
            answer_index: answerIndex
          });
        }
      }
    } catch (err) {
      console.error('Error submitting answer:', err);
      showError(err.response?.data?.message || 'Failed to submit answer');
    } finally {
      setSyncing(false);
    }
  };

  // Host actions
  const handleShowAnswers = async () => {
    if (!isHost) return;
    
    try {
      console.log('Host requesting to show answers...');
      const response = await api.post(`/multiplayer/lobbies/${lobbyId}/toggle-answers`, {
        show_answers: true
      });
      
      if (response.data.status === "ok") {
        console.log('Answers shown successfully, fetching correct answer...');
        setShowAnswers(true);
        
        // Небольшая задержка для обеспечения правильного порядка загрузки
        setTimeout(() => {
          fetchCorrectAnswer(currentQuestion._id);
        }, 500);
        
        // Notify other participants via socket
        sendSocketEvent('show_correct_answer', {
          lobby_id: lobbyId,
          question_id: currentQuestion._id
        });
      }
    } catch (err) {
      console.error('Error showing answers:', err);
      showError(err.response?.data?.message || 'Failed to show answers');
    }
  };

  const handleNextQuestion = async () => {
    if (!isHost) return;
    
    try {
      const response = await api.post(`/multiplayer/lobbies/${lobbyId}/next-question`, {
        lobby_id: lobbyId
      });
      
      if (response.data.status === "ok") {
        // Reset states for new question
        setShowAnswers(false);
        setAnswerSubmitted(false);
        setSelectedAnswer(null);
      setCorrectAnswer(null);
      setExplanation(null);
      setAfterAnswerMedia(null);
        setAfterAnswerMediaType('image');
        setParticipantAnswers({});
        
        // Update question index
        setCurrentQuestionIndex(prev => prev + 1);
        
        // Fetch new question
        fetchCurrentQuestion();
        
        // Notify other participants via socket
        sendSocketEvent('next_question', {
          lobby_id: lobbyId,
          question_index: currentQuestionIndex + 1
        });
      }
    } catch (err) {
      console.error('Error moving to next question:', err);
      showError(err.response?.data?.message || 'Failed to move to next question');
    }
  };

  const handleCloseLobby = async () => {
    if (!isHost) return;
    
    if (!confirm(t['confirmCloseLobby'] || 'Are you sure you want to close this lobby?')) {
      return;
      }
      
      try {
      const response = await api.post(`/multiplayer/lobbies/${lobbyId}/close`);
        
        if (response.data.status === "ok") {
        sendSocketEvent('close_lobby', { lobby_id: lobbyId });
        
        setTimeout(() => {
          navigate('/dashboard', { replace: true });
        }, 1500);
      } else {
        setError(response.data.message || t['failedToCloseLobby'] || 'Failed to close lobby');
      }
    } catch (error) {
      console.error('Error closing lobby:', error);
      setError(error.response?.data?.message || t['failedToCloseLobby'] || 'Failed to close lobby');
    }
  };

  // User actions
  const handleLeaveLobby = async () => {
    if (!confirm('Вы действительно хотите выйти из лобби?')) {
      return;
    }
    
    try {
      const response = await api.post(`/multiplayer/lobbies/${lobbyId}/leave`);
      
      if (response.data.status === 'ok') {
        // Отправляем событие в сокет о выходе
        sendSocketEvent('leave_lobby', { 
          lobby_id: lobbyId, 
          user_id: currentUserId 
        });
        
        // Отключаем сокет
        disconnectSocket();
        
        // Очищаем localStorage
        localStorage.removeItem('token');
        localStorage.removeItem('isGuest');
        localStorage.removeItem('ws_token');
        delete api.defaults.headers.common['Authorization'];
        
        // Перенаправляем пользователя
        navigate('/dashboard', { replace: true });
        } else {
        setError(response.data.message || 'Не удалось выйти из лобби');
      }
    } catch (error) {
      console.error('Error leaving lobby:', error);
      setError(error.response?.data?.message || 'Не удалось выйти из лобби');
    }
  };

  // Guest leave
  const handleGuestLeave = async () => {
    if (!confirm('Вы действительно хотите выйти из лобби?')) {
      return;
    }
    
    try {
      const response = await api.post(`/multiplayer/lobbies/${lobbyId}/leave`);
      
      if (response.data.status === 'ok') {
        // Отправляем событие в сокет о выходе
        sendSocketEvent('leave_lobby', { 
          lobby_id: lobbyId, 
          user_id: currentUserId 
        });
        
        // Отключаем сокет
        disconnectSocket();
        
        // Очищаем localStorage
        localStorage.removeItem('token');
        localStorage.removeItem('isGuest');
        localStorage.removeItem('ws_token');
        delete api.defaults.headers.common['Authorization'];
        
        // Перенаправляем гостя на главную
        navigate('/', { replace: true });
      } else {
        setError(response.data.message || 'Не удалось выйти из лобби');
      }
    } catch (error) {
      console.error('Error leaving lobby:', error);
      setError(error.response?.data?.message || 'Не удалось выйти из лобби');
    }
  };

  // Fetch current question when component mounts or question index changes
  useEffect(() => {
    if (lobbyInfo && lobbyId && lobbyInfo.status !== 'finished') {
      console.log('Fetching current question, lobbyInfo:', lobbyInfo, 'currentQuestionIndex:', currentQuestionIndex);
      fetchCurrentQuestion();
    }
  }, [lobbyId, currentQuestionIndex, lobbyInfo]); // Убираем fetchCurrentQuestion из зависимостей

  // Category icons mapping
  const getCategoryIcon = (categories) => {
    if (categories.includes('A1') || categories.includes('A') || categories.includes('B1')) {
      return <MdDirectionsBike size={20} />;
    }
    if (categories.includes('B') || categories.includes('BE')) {
      return <MdDirectionsCar size={20} />;
    }
    if (categories.includes('C') || categories.includes('C1')) {
      return <FaTruck size={20} />;
    }
    if (categories.includes('BC1')) {
      return <FaTruckMoving size={20} />;
    }
    if (categories.includes('D1') || categories.includes('D') || categories.includes('Tb')) {
      return <FaBusAlt size={20} />;
    }
    if (categories.includes('CE') || categories.includes('DE')) {
      return <MdLocalShipping size={20} />;
    }
    if (categories.includes('Tm')) {
      return <MdTimer size={20} />;
    }
    return <MdDirectionsCar size={20} />;
  };

  // Toggle sidebars
  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);
  const toggleQuestionNav = () => setIsQuestionNavOpen(!isQuestionNavOpen);
  const closeQuestionNav = () => setIsQuestionNavOpen(false);

  // Report functionality
  const handleOpenReport = () => {
    setShowReportModal(true);
    setReportData({ type: '', description: '' });
  };

  const handleCloseReport = () => {
    setShowReportModal(false);
    setReportData({ type: '', description: '' });
  };

  const handleSubmitReport = async (e) => {
    e.preventDefault();
    if (!reportData.type || !reportData.description.trim()) return;

    setReportSubmitting(true);
    try {
      await api.post(`/report/test/submit`, {
        lobby_id: lobbyId,
        question_id: currentQuestion._id,
        report_type: reportData.type,
        description: reportData.description
      });
      
      notify.success(t['reportSubmittedSuccessfully'] || 'Report submitted successfully', { important: true });
      handleCloseReport();
    } catch (err) {
      console.error('Error submitting report:', err);
      notify.error(t['reportSubmissionFailed'] || 'Failed to submit report. Please try again.');
    } finally {
      setReportSubmitting(false);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className={`multiplayer-test-page ${isDark ? 'dark-theme' : ''}`}>
        <LobbyHeader isGuest={isGuest} />
          <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>{t['loading'] || 'Loading...'}</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`multiplayer-test-page ${isDark ? 'dark-theme' : ''}`}>
        <LobbyHeader isGuest={isGuest} />
        <div className="error-container">
          <FaExclamationTriangle />
          <p>{error}</p>
          <button className="back-btn" onClick={() => navigate('/dashboard')}>
            <FaArrowLeft />
            {t['backToDashboard'] || 'Back to Dashboard'}
            </button>
        </div>
      </div>
    );
  }

  // Test completed - show loading while redirecting
  if (testCompleted) {
    return (
      <div className={`multiplayer-test-page ${isDark ? 'dark-theme' : ''}`}>
        <LobbyHeader isGuest={isGuest} />
          <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Переход к результатам...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`multiplayer-test-page ${isDark ? 'dark-theme' : ''}`}>
      <LobbyHeader isGuest={isGuest} />
      
      {/* Sync indicator */}
      {syncing && (
        <div className="sync-indicator">
          <div className="sync-spinner"></div>
          <span>{t['syncingWithServer'] || 'Syncing with server...'}</span>
        </div>
      )}
      
      {/* Question Navigation Overlay */}
      <div 
        className={`question-nav-overlay ${isQuestionNavOpen ? 'open' : ''}`}
        onClick={closeQuestionNav}
      />
      
      <div className="main-content">
        <div className="test-page">
          {/* Test Header with Question Number and Connection Status */}
          <div className="test-header">
            <div className="test-progress">
              <div className="progress-text">
                {t['question'] || 'Question'} {currentQuestionIndex + 1} {t['of'] || 'of'} {totalQuestions}
              </div>
              <div className="progress-bar">
                <div 
                  className="progress" 
                  style={{ width: `${((currentQuestionIndex + 1) / totalQuestions) * 100}%` }}
                ></div>
              </div>
            </div>
            
            <div className="header-controls">
              {/* Connection Status */}
              <div className="connection-status-inline">
                {wsConnected ? (
                  <div className="status-indicator online">
                    <FaWifi />
                    <span>{t['connected'] || 'Connected'}</span>
                  </div>
                ) : (
                  <div className="status-indicator offline">
                    <FaExclamationTriangle />
                    <span>{t['connecting'] || 'Connecting...'}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
          
          {/* Test Content */}
          <div className="test-content">
            {/* Question Navigation Sidebar */}
            <div className={`question-nav-sidebar ${isQuestionNavOpen ? 'open' : ''}`}>
              <button className="nav-close-btn" onClick={closeQuestionNav} title="Закрыть">
                ×
              </button>
              
              <div className="nav-header">
                <div className="nav-title">{t['questionNavigator'] || 'Question Navigator'}</div>
                <div className="nav-subtitle">
                  {Object.keys(myAnswers).length}/{totalQuestions} {t['answered'] || 'answered'}
                </div>
              </div>
              
              <div className="question-grid">
                {Array.from({ length: totalQuestions }, (_, index) => {
                  const isAnswered = myAnswers[`question_${index}`] !== undefined;
                  const isCurrent = index === currentQuestionIndex;
                  
                  let className = 'question-nav-item';
                  if (isCurrent) className += ' active';
                  if (isAnswered) className += ' answered';
                  
                  return (
                    <div 
                      key={index} 
                      className={className}
                      onClick={() => {
                        if (isAnswered || isCurrent) {
                          setCurrentQuestionIndex(index);
                          if (window.innerWidth <= 1024) {
                            setIsQuestionNavOpen(false);
                          }
                        }
                      }}
                      style={{ 
                        cursor: (isAnswered || isCurrent) ? 'pointer' : 'not-allowed',
                        opacity: (isAnswered || isCurrent) ? 1 : 0.5
                      }}
                    >
                      {index + 1}
                    </div>
                  );
                })}
              </div>
            </div>
            
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
                  <div className="question-media">
                    <div className="media-container stable-container">
                      {mediaLoading ? (
                        <div className="loading-container" style={{ height: '100%', width: '100%' }}>
                          <div className="loading-bar-container">
                            <div className="loading-bar"></div>
                          </div>
                          <div className="loading-text">{t['loadingMedia'] || 'Loading media...'}</div>
                        </div>
                      ) : (
                        <QuestionMedia
                          currentQuestion={currentQuestion}
                          answerSubmitted={answerSubmitted}
                          afterAnswerMedia={afterAnswerMedia}
                          afterAnswerMediaType={afterAnswerMediaType}
                          videoRef={videoRef}
                          afterVideoRef={afterVideoRef}
                          getTranslation={(key) => t[key] || key}
                        />
                      )}
                    </div>
                  </div>
                  
                  {/* Answer Options */}
                  <div className="answer-options">
                    {currentQuestion.answers && currentQuestion.answers.map((answer, index) => {
                      const answerText = localizeText(answer);
                      let answerClass = "answer-option";
                      const isMyAnswer = selectedAnswer === index;
                      const isCorrectAnswer = correctAnswer?.index === index;
                      const isAnswered = answerSubmitted;
                      
                      if (isAnswered && showAnswers) {
                        // Показываем правильность ответов когда ответы показаны
                        if (isMyAnswer && isCorrectAnswer) {
                          answerClass += " correct";
                        } else if (isMyAnswer && !isCorrectAnswer) {
                          answerClass += " incorrect";
                        } else if (isCorrectAnswer) {
                          answerClass += " correct";
                        }
                      } else if (isMyAnswer) {
                        answerClass += " selected";
                      }
                      
                      // Add orange styling if user answered this option
                      if (isMyAnswer && isAnswered) {
                        answerClass += " answered";
                      }
                      
                      return (
                        <div 
                          key={index} 
                          className={answerClass}
                          onClick={() => !answerSubmitted && handleAnswerSubmit(index)}
                          tabIndex={answerSubmitted ? -1 : 0}
                          onKeyPress={(e) => {
                            if (e.key === 'Enter' && !answerSubmitted) {
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
                  
                  {/* Explanation */}
                  {answerSubmitted && explanation && (
                    <div className="answer-explanation">
                      <div className="explanation-header">
                        <FaLightbulb />
                        <div className="explanation-title">{t['explanation'] || 'Explanation'}</div>
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
          
          {/* Host Controls Section */}
          {isHost && (
            <div className="host-controls-section">
              <div className="host-controls-header">
                <FaCrown />
                <span>{t['hostControls'] || 'Host Controls'}</span>
              </div>
              
              <div className="host-controls">
                <button 
                  className="action-btn show-answers-btn"
                  onClick={handleShowAnswers}
                  disabled={showAnswers}
                  title={t['showAnswers'] || 'Show answers'}
                >
                  <FaEye />
                  <span>{t['showAnswers'] || 'Show answers'}</span>
                </button>
                
                <button 
                  className="action-btn next-question-btn"
                  onClick={handleNextQuestion}
                  disabled={currentQuestionIndex >= totalQuestions - 1}
                  title={t['nextQuestion'] || 'Next question'}
                >
                  <FaArrowRight />
                  <span>{t['nextQuestion'] || 'Next question'}</span>
                </button>
                
                <button 
                  className="action-btn close-lobby-btn"
                  onClick={handleCloseLobby}
                  title={t['closeLobby'] || 'Close lobby'}
                >
                  <FaTimes />
                  <span>{t['closeLobby'] || 'Close lobby'}</span>
                </button>
              </div>
            </div>
          )}
          
          {/* Participants Section */}
          <div className="participants-section">
            <div className="participants-header">
              <FaUsers />
              <span>{t['participants'] || 'Participants'}</span>
              <span className="participants-count">
                {participants.length}/{lobbyInfo?.max_participants || 8}
              </span>
            </div>
            
            <div className="participants-list">
              {Array.isArray(participants) && participants.map((participant) => {
                const participantAnswer = participantAnswers[participant.user_id];
                const hasAnswered = participantAnswer !== undefined && participantAnswer !== null;
                const isCorrect = hasAnswered && participantAnswer === correctAnswer?.index;
                
                return (
                  <div 
                    key={participant.user_id}
                    className={`participant-item ${!onlineUsers.includes(participant.user_id) ? 'offline' : ''} ${hasAnswered ? 'answered' : ''}`}
                  >
                    <div className="participant-info">
                      <div className="participant-avatar">
                        {participant.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="participant-details">
                        <span className="participant-name">{participant.name}</span>
                        <span className="participant-status">
                          <div className={`status-dot ${onlineUsers.includes(participant.user_id) ? 'online' : 'offline'}`}></div>
                          {participant.is_host ? (
                            <>
                              {lobbyInfo?.host_subscription_type === 'royal' ? <FaCrown /> : <FaGraduationCap />}
                              {t['host'] || 'Host'}
                            </>
                          ) : (
                            <>
                              {onlineUsers.includes(participant.user_id) ? (t['online'] || 'Online') : (t['offline'] || 'Offline')}
                            </>
                          )}
                        </span>
                        {hasAnswered && (
                          <span className="participant-answer">
                            {isHost ? (
                              // Host sees which answer each participant chose
                              <span className={`answer-badge ${isCorrect ? 'correct' : 'incorrect'}`}>
                                {String.fromCharCode(65 + participantAnswer)}
                              </span>
                            ) : (
                              // Other participants only see that someone answered
                              <span className="answer-badge answered">
                                ✓
                              </span>
                            )}
                          </span>
                        )}
                        {!hasAnswered && showAnswers && (
                          <span className="participant-answer">
                            <span className="answer-badge not-answered">
                              {t['notAnswered'] || 'Не ответил'}
                            </span>
                          </span>
                        )}
                        {!hasAnswered && showAnswers && (
                          <span className="participant-answer">
                            <span className="answer-badge not-answered">
                              {t['notAnswered'] || 'Не ответил'}
                            </span>
                          </span>
                        )}
                      </div>
                    </div>
                    
                    {isHost && !participant.is_host && (
              <button 
                        className="kick-btn"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          // Handle kick participant
                        }}
                        title={t['kickUser'] || 'Kick user'}
                      >
                        <FaUserTimes />
              </button>
            )}
                  </div>
                );
              })}
            </div>
          </div>
          
          {/* User Actions */}
          {!isHost && (
            <div className="user-actions-section">
              <button 
                className="action-btn leave-btn"
                onClick={() => isGuest ? handleGuestLeave() : handleLeaveLobby()}
                title={t['leaveLobby'] || 'Leave lobby'}
              >
                <FaSignOutAlt />
                <span>{t['leaveLobby'] || 'Leave lobby'}</span>
              </button>
            </div>
          )}
        </div>
      </div>
      
      {/* Report Modal */}
      {showReportModal && (
        <div className="report-modal-overlay" onClick={handleCloseReport}>
          <div className="report-modal" onClick={(e) => e.stopPropagation()}>
            <div className="report-modal-header">
              <div className="report-modal-title">{t['reportQuestion'] || 'Report Question'}</div>
              <div className="report-modal-subtitle">
                {t['question'] || 'Question'} {currentQuestionIndex + 1}: {t['helpUsImprove'] || 'Help us improve'}
              </div>
            </div>
            
            <form className="report-form" onSubmit={handleSubmitReport}>
              <div className="form-group">
                <label className="form-label">{t['reportType'] || 'Report Type'}</label>
                <select 
                  className="form-select"
                  value={reportData.type}
                  onChange={(e) => setReportData({...reportData, type: e.target.value})}
                  required
                >
                  <option value="">{t['selectReportType'] || 'Select report type'}</option>
                  <option value="incorrect_answer">{t['incorrectAnswer'] || 'Incorrect answer'}</option>
                  <option value="unclear_question">{t['unclearQuestion'] || 'Unclear question'}</option>
                  <option value="technical_error">{t['technicalIssue'] || 'Technical issue'}</option>
                  <option value="inappropriate_content">{t['inappropriateContent'] || 'Inappropriate content'}</option>
                  <option value="other">{t['other'] || 'Other'}</option>
                </select>
              </div>
              
              <div className="form-group">
                <label className="form-label">{t['description'] || 'Description'}</label>
                <textarea 
                  className="form-textarea"
                  value={reportData.description}
                  onChange={(e) => setReportData({...reportData, description: e.target.value})}
                  placeholder={t['describeIssue'] || 'Describe the issue'}
                  required
                />
              </div>
              
              <div className="report-modal-actions">
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={handleCloseReport}
                  disabled={reportSubmitting}
                >
                  {t['cancel'] || 'Cancel'}
                </button>
                <button 
                  type="submit" 
                  className="btn btn-danger"
                  disabled={reportSubmitting || !reportData.type || !reportData.description.trim()}
                >
                  {reportSubmitting ? t['submitting'] || 'Submitting' : t['submitReport'] || 'Submit Report'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      
      {/* Kick/Close Modal */}
      {modalMessage && (
        <div className="modal-overlay">
          <div className="modal-content">
            <FaExclamationTriangle className="modal-icon" />
            <h3>{modalMessage.title}</h3>
            <p>{modalMessage.message}</p>
            <button 
              onClick={() => navigate(modalMessage.redirectPath, { replace: true })}
              className="modal-button"
            >
              {modalMessage.buttonText}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default MultiplayerTestPage; 