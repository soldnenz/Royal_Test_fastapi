import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  FaTimes, FaCheck, FaArrowLeft, FaArrowRight, FaFlag, 
  FaLanguage, FaMoon, FaSun, FaHistory, FaExclamationTriangle,
  FaPlay, FaPause, FaVolumeUp, FaVolumeMute, FaExpand,
  FaBars, FaQuestionCircle, FaLightbulb, FaClock, FaStar, FaChartBar, FaUser
} from 'react-icons/fa';
import api from '../utils/axios';
import { notify } from '../components/notifications/NotificationSystem';
import DashboardHeader from '../components/dashboard/DashboardHeader';
import DashboardSidebar from '../components/dashboard/DashboardSidebar';
import { getCurrentTheme, toggleTheme, initTheme } from '../utils/themeUtil';
import { getCurrentLanguage, setLanguage, getTranslation, localizeText, LANGUAGES } from '../utils/languageUtil';
import './dashboard/styles.css';
import './TestPage.css';

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
  isExamMode,
  afterAnswerMedia,
  afterAnswerMediaType,
  videoRef,
  afterVideoRef,
  getTranslation
}) => {
  const mediaUrl = answerSubmitted && !isExamMode && afterAnswerMedia 
    ? afterAnswerMedia 
    : currentQuestion?.media_url;

  const mediaType = answerSubmitted && !isExamMode && afterAnswerMedia
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
      <video className="fallback-video" src="/static/no_image.MP4" preload="metadata" playsInline muted loop autoPlay />
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
      <img src={loadedSrc} key={loadedSrc} alt="Question Media" className="question-image" />
    );
  }
});


const TestPage = () => {
  const { lobbyId } = useParams();
  const navigate = useNavigate();
  const [theme, setTheme] = useState(getCurrentTheme());
  const [language, setCurrentLanguage] = useState(getCurrentLanguage());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [questions, setQuestions] = useState([]);
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
  const [afterAnswerMediaType, setAfterAnswerMediaType] = useState('image'); // 'image' или 'video'
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
  const [answerDetailsCache, setAnswerDetailsCache] = useState({});
  
  const intervalRef = useRef(null);
  const videoRef = useRef(null);
  const afterVideoRef = useRef(null);
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

  // Handle test completion redirect
  useEffect(() => {
    if (testCompleted) {
      navigate(`/test-results/${lobbyId}`);
    }
  }, [testCompleted, navigate, lobbyId]);

  // Theme toggle
  const handleToggleTheme = () => {
    const newTheme = toggleTheme();
    setTheme(newTheme);
    document.body.classList.toggle('dark-theme', newTheme === 'dark');
  };

  // Language change
  const handleChangeLanguage = (newLanguage) => {
    if (setLanguage(newLanguage)) {
      setCurrentLanguage(newLanguage);
      window.dispatchEvent(new Event('languageChange'));
    }
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

  // Toggle sidebars
  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);
  const toggleQuestionNav = () => setIsQuestionNavOpen(!isQuestionNavOpen);
  
  // Close navigation when clicking overlay
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
      // Отправляем жалобу на новый защищённый эндпоинт
      await api.post(`/report/test/submit`, {
        lobby_id: lobbyId,
        question_id: questions[currentQuestionIndex],
        report_type: reportData.type,
        description: reportData.description
      });
      
      // Уведомление об успешной отправке
      notify.success(getTranslation('reportSubmittedSuccessfully') || 'Report submitted successfully', { important: true });
      handleCloseReport();
    } catch (err) {
      console.error('Error submitting report:', err);
      notify.error(getTranslation('reportSubmissionFailed') || 'Failed to submit report. Please try again.');
    } finally {
      setReportSubmitting(false);
    }
  };

  // Fetch lobby information with security checks
  useEffect(() => {
    const fetchLobbyInfo = async () => {
      // Prevent duplicate requests
      if (fetchLobbyInfo.isLoading) {
        console.log(`[DEBOUNCE] Skipping duplicate lobby info request for ${lobbyId}`);
        return;
      }
      
      fetchLobbyInfo.isLoading = true;
      
      try {
        console.log(`[SECURITY] Fetching secure lobby info for ID: ${lobbyId}`);
        setSyncing(true);
        
        // Use new secure endpoint
        const response = await api.get(`/lobby_solo/${lobbyId}/secure`);
        
        if (response.data.status === "ok") {
          console.log("[SECURITY] Secure lobby info loaded successfully:", response.data.data);
          setLobbyInfo(response.data.data);
          
          if (response.data.data.status === 'finished' || response.data.data.status === 'inactive') {
            setTestCompleted(true);
            fetchTestResults();
            return;
          }
          
          setIsExamMode(response.data.data.exam_mode === true);
          
          // Initialize exam timer if in exam mode
          if (response.data.data.exam_mode && response.data.data.exam_timer) {
            const serverTimeLeft = response.data.data.exam_timer.time_left;
            setTimeLeft(serverTimeLeft);
            localStorage.setItem(`exam_timer_${lobbyId}`, serverTimeLeft.toString());
            
            // Only auto-close if time is significantly expired (more than 1 minute past)
            // This prevents immediate finish on page load due to small time discrepancies
            if (serverTimeLeft < -60) {
              console.log("[SECURITY] Exam time significantly expired, auto-closing lobby");
              await api.post(`/lobby_solo/${lobbyId}/secure/auto-close-exam`);
              setTestCompleted(true);
              fetchTestResults();
              return;
            }
          }
          
          if (response.data.data.question_ids && response.data.data.question_ids.length > 0) {
            setQuestions(response.data.data.question_ids);
            
            const serverAnswers = response.data.data.user_answers || {};
            let localAnswers = {};
            const savedAnswers = localStorage.getItem(`userAnswers_${lobbyId}`);
            if (savedAnswers) {
              try {
                localAnswers = JSON.parse(savedAnswers);
              } catch (e) {
                console.error("[SECURITY] Error parsing saved answers:", e);
              }
            }
            
            const mergedAnswers = { ...localAnswers, ...serverAnswers };
            
            if (Object.keys(mergedAnswers).length > 0) {
              setUserAnswers(mergedAnswers);
              localStorage.setItem(`userAnswers_${lobbyId}`, JSON.stringify(mergedAnswers));
              
              const answeredQuestionIds = Object.keys(mergedAnswers);
              if (answeredQuestionIds.length > 0) {
                const lastAnsweredId = answeredQuestionIds[answeredQuestionIds.length - 1];
                const lastAnsweredIndex = response.data.data.question_ids.indexOf(lastAnsweredId);
                const nextIndex = Math.min(lastAnsweredIndex + 1, response.data.data.question_ids.length - 1);
                setCurrentQuestionIndex(nextIndex);
                localStorage.setItem(`currentQuestionIndex_${lobbyId}`, nextIndex.toString());
              }
            }
          }
        } else {
          showError(response.data.message || 'Failed to load test information');
        }
        
        setLoading(false);
        setSyncing(false);
        fetchLobbyInfo.isLoading = false;
      } catch (err) {
        console.error('[SECURITY] Error fetching secure lobby info:', err);
        showError(err.response?.data?.message || 'Failed to load test information');
        setLoading(false);
        setSyncing(false);
        fetchLobbyInfo.isLoading = false;
      }
    };

    fetchLobbyInfo();
  }, [lobbyId]);

  // Fetch current question with security checks
  const fetchCurrentQuestion = async () => {
    console.log('[CALL] fetchCurrentQuestion start');
    if (!questions.length || currentQuestionIndex >= questions.length) {
        console.log('[CALL] fetchCurrentQuestion end - no questions or index out of bounds.');
        return;
    }
    
    const questionId = questions[currentQuestionIndex];
    
    // Prevent duplicate requests for the same question
    const requestKey = `${questionId}_${currentQuestionIndex}`;
    if (fetchCurrentQuestion.requestKey === requestKey && fetchCurrentQuestion.isLoading) {
      console.log(`[DEBOUNCE] Skipping duplicate request for question ${questionId}`);
      console.log('[CALL] fetchCurrentQuestion end - debounced.');
      return;
    }
    
    fetchCurrentQuestion.requestKey = requestKey;
    fetchCurrentQuestion.isLoading = true;
    
    try {
      setMediaLoading(true);
      setVideoError(false);
      
      // Add loading class to prevent container collapse
      const mediaContainers = document.querySelectorAll('.media-container');
      mediaContainers.forEach(container => container.classList.add('loading'));
      
      console.log(`[SECURITY] Fetching secure question: ${questionId}, index: ${currentQuestionIndex}`);
      
      // Use new secure endpoint with answer validation
              const response = await api.get(`/lobby_solo/${lobbyId}/questions/${questionId}/secure`, {
        params: {
          current_index: currentQuestionIndex,
          user_answers: JSON.stringify(userAnswers)
        }
      });
      console.log(`[API] GET /lobby_solo/${lobbyId}/questions/${questionId}/secure`, response.data);
      
      if (response.data.status === "ok") {
        const questionData = response.data.data;
        
        console.log(`[SECURITY] Question ${questionId} loaded securely:`, questionData);
        console.log(`[SECURITY] Question answers:`, questionData.answers);
        
        // Security: Only show media if user has access
        if (questionData.has_media && questionData.media_access_granted) {
          // Используем обновленный solo_files_router для безопасного доступа к медиа
          // Кэшируем URL для предотвращения повторных запросов
          const mediaUrl = `/api/files_solo/secure/media/${questionId}?lobby_id=${lobbyId}`;
          console.log(`[MEDIA] Setting media URL for question ${questionId}: ${mediaUrl}`);
          questionData.media_url = mediaUrl;
          
          // Determine media type
          if (questionData.media_filename) {
            const filename = questionData.media_filename.toLowerCase();
            if (filename.endsWith('.mp4') || filename.endsWith('.webm') || filename.endsWith('.mov')) {
              questionData.media_type = 'video';
            } else {
              questionData.media_type = 'image';
            }
          } else {
            questionData.media_type = 'image';
          }
        } else if (questionData.has_media && !questionData.media_access_granted) {
          console.log(`[SECURITY] Media access denied for question ${questionId}`);
          questionData.media_url = null;
          questionData.media_type = 'restricted';
        }
        
        setCurrentQuestion(questionData);
        setAnswerSubmitted(false);
        setSelectedAnswer(null);
        setCorrectAnswer(null);
        setExplanation(null);
        setAfterAnswerMedia(null);
        setAfterAnswerMediaType('image');
        
        if (userAnswers[questionId] !== undefined) {
          setSelectedAnswer(userAnswers[questionId]);
          setAnswerSubmitted(true);
          
          // Security: Only show answer if allowed in current mode
          const shouldShowAnswer = !isExamMode && questionData.answer_access_granted;
          
          if (shouldShowAnswer) {
            fetchCorrectAnswerSecure(questionId);
          }
        }
        
        setMediaLoading(false);
        fetchCurrentQuestion.isLoading = false;
        
        // Remove loading class
        const mediaContainers = document.querySelectorAll('.media-container');
        mediaContainers.forEach(container => container.classList.remove('loading'));
      } else {
        console.error(`[SECURITY] Failed to load question ${questionId}:`, response.data.message);
        showError(response.data.message || 'Failed to load question');
        setMediaLoading(false);
        fetchCurrentQuestion.isLoading = false;
        
        // Remove loading class
        const mediaContainers = document.querySelectorAll('.media-container');
        mediaContainers.forEach(container => container.classList.remove('loading'));
      }
    } catch (err) {
      console.error('[SECURITY] Error fetching secure question:', err);
      
      if (err.response?.status === 403) {
        console.log(`[SECURITY] Access denied for question ${questionId}:`, err.response.data.message);
        showError('Доступ запрещен. Ответьте на текущий вопрос.');
      } else if (err.response?.status === 429) {
        console.log(`[SECURITY] Rate limit exceeded for question ${questionId}`);
        showError('Слишком много запросов. Подождите немного.');
      } else {
        showError(err.response?.data?.message || 'Failed to load question');
      }
      setMediaLoading(false);
      fetchCurrentQuestion.isLoading = false;
      
      // Remove loading class
      const mediaContainers = document.querySelectorAll('.media-container');
      mediaContainers.forEach(container => container.classList.remove('loading'));
    }
    console.log('[CALL] fetchCurrentQuestion end');
  };

  // Save user answers to localStorage
  useEffect(() => {
    if (Object.keys(userAnswers).length > 0) {
      localStorage.setItem(`userAnswers_${lobbyId}`, JSON.stringify(userAnswers));
    }
  }, [userAnswers, lobbyId]);

  // Timer for exam mode with auto-close protection
  useEffect(() => {
    if (isExamMode && !testCompleted) {
      // Fetch initial timer state from server
      const fetchTimerState = async () => {
        try {
          const response = await api.get(`/lobby_solo/${lobbyId}/secure/exam-timer`);
          if (response.data.status === "ok") {
            const serverTimeLeft = response.data.data.time_left;
            setTimeLeft(serverTimeLeft);
            localStorage.setItem(`exam_timer_${lobbyId}`, serverTimeLeft.toString());
            
            // Only auto-finish if time is significantly expired (more than 1 minute past)
            // This prevents immediate finish on page load due to small time discrepancies
            if (serverTimeLeft < -60) {
              console.log('[SECURITY] Exam time significantly expired from server');
              finishTestSecure();
              return;
            }
          }
        } catch (err) {
          console.error('[SECURITY] Error fetching secure timer state:', err);
          const savedTimeLeft = localStorage.getItem(`exam_timer_${lobbyId}`);
          if (savedTimeLeft) {
            const timeLeft = parseInt(savedTimeLeft, 10);
            setTimeLeft(Math.max(0, timeLeft));
          } else {
            // Default to full exam time if no saved state
            setTimeLeft(40 * 60);
          }
        }
      };

      fetchTimerState();

      // Start countdown timer
      intervalRef.current = setInterval(() => {
        setTimeLeft(prevTime => {
          const newTime = prevTime <= 1 ? 0 : prevTime - 1;
          localStorage.setItem(`exam_timer_${lobbyId}`, newTime.toString());
          
          if (newTime <= 0) {
            console.log('[SECURITY] Exam time expired - auto-finishing test');
            clearInterval(intervalRef.current);
            finishTestSecure();
            return 0;
          }
          return newTime;
        });
      }, 1000);

      // Sync with server every 30 seconds
      const syncInterval = setInterval(async () => {
        try {
          const currentTimeLeft = parseInt(localStorage.getItem(`exam_timer_${lobbyId}`) || '0', 10);
          await api.post(`/lobby_solo/${lobbyId}/secure/exam-timer`, {
            time_left: currentTimeLeft
          });
        } catch (err) {
          console.error('[SECURITY] Error syncing secure timer with server:', err);
        }
      }, 30000);

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
        clearInterval(syncInterval);
      };
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isExamMode, testCompleted, lobbyId]);

  const fetchCorrectAnswerSecure = async (questionId, updatedAnswersParam = null) => {
    console.log('[CALL] fetchCorrectAnswerSecure start', { questionId, updatedAnswersParam: !!updatedAnswersParam });

    // 1. Check cache first
    if (answerDetailsCache[questionId]) {
      console.log(`[CACHE] Using cached answer details for question ${questionId}`);
      const cachedData = answerDetailsCache[questionId];
      setCorrectAnswer(cachedData.correctAnswer);
      setExplanation(cachedData.explanation);
      if (cachedData.afterAnswerMedia) {
        setAfterAnswerMedia(cachedData.afterAnswerMedia);
        setAfterAnswerMediaType(cachedData.afterAnswerMediaType);
      } else {
        setAfterAnswerMedia(null);
        setAfterAnswerMediaType('image');
      }
      console.log('[CALL] fetchCorrectAnswerSecure end (from cache)');
      return;
    }

    if (fetchCorrectAnswerSecure.isLoading && fetchCorrectAnswerSecure.currentQuestionId === questionId) {
      console.log(`[DEBOUNCE] Skipping duplicate correct answer request for question ${questionId}`);
      return;
    }
    
    fetchCorrectAnswerSecure.isLoading = true;
    fetchCorrectAnswerSecure.currentQuestionId = questionId;
    
    try {
      console.log(`[SECURITY] Fetching secure correct answer for question: ${questionId}`);
      
      const currentAnswers = updatedAnswersParam || userAnswers;
      
      console.log(`[DEBUG] currentAnswers for correct-answer check:`, currentAnswers);
      
      // 2. Fetch correct answer data
      const response = await api.get(`/lobby_solo/${lobbyId}/secure/correct-answer`, {
        params: { 
          question_id: questionId,
          user_answers: JSON.stringify(currentAnswers),
          exam_mode: isExamMode
        }
      });
      console.log(`[API] GET /lobby_solo/${lobbyId}/secure/correct-answer`, response.data);
      
      if (response.data.status === "ok") {
        const correctData = response.data.data;
        console.log('[SECURITY] Received secure correct answer data:', correctData);
        
        if (isExamMode && correctData.correct_answer_index !== undefined) {
          console.error('[SECURITY] VIOLATION: Correct answer leaked in exam mode!');
          fetchCorrectAnswerSecure.isLoading = false;
          return;
        }
        
        const newCorrectAnswer = {
          index: correctData.correct_answer_index,
          hasAfterAnswerMedia: correctData.has_after_answer_media
        };
        setCorrectAnswer(newCorrectAnswer);
        
        const newExplanation = correctData.explanation && Object.keys(correctData.explanation).length > 0 ? correctData.explanation : null;
        setExplanation(newExplanation);

        let newAfterAnswerMedia = null;
        let newAfterAnswerMediaType = 'image';
        
        // 3. Merged logic to fetch after-answer media
        if (correctData.has_after_answer_media && correctData.after_media_access_granted) {
          console.log('[SECURITY] Fetching secure after answer media for question:', questionId);
          
          try {
              setVideoError(false);
              const accessResponse = await api.get(`/lobby_solo/${lobbyId}/secure/after-answer-media-access`, {
                params: {
                  question_id: questionId,
                  user_answers: JSON.stringify(currentAnswers)
                }
              });
              console.log(`[API] GET /lobby_solo/${lobbyId}/secure/after-answer-media-access`, accessResponse.data);

              if (accessResponse.data.status === "ok" && accessResponse.data.data.access_granted) {
                const questionResponse = await api.get(`/lobby_solo/${lobbyId}/questions/${questionId}/secure`, {
                  params: {
                    current_index: currentQuestionIndex,
                    user_answers: JSON.stringify(currentAnswers)
                  }
                });
                console.log(`[API] GET /lobby_solo/${lobbyId}/questions/${questionId}/secure (for after media)`, questionResponse.data);

                if (questionResponse.data.status === "ok") {
                  const questionData = questionResponse.data.data;
                  newAfterAnswerMedia = `/api/files_solo/secure/after-answer-media/${questionId}?lobby_id=${lobbyId}`;
                  setAfterAnswerMedia(newAfterAnswerMedia);

                  if (questionData.after_answer_media_filename) {
                    const filename = questionData.after_answer_media_filename.toLowerCase();
                    if (filename.endsWith('.mp4') || filename.endsWith('.webm') || filename.endsWith('.mov')) {
                      newAfterAnswerMediaType = 'video';
                    }
                  }
                  setAfterAnswerMediaType(newAfterAnswerMediaType);
                }
              }
          } catch (err) {
              console.error('[SECURITY] Error fetching secure after-answer media:', err);
              setAfterAnswerMedia(null);
              setAfterAnswerMediaType('image');
              setVideoError(false);
          }
        }
        
        // 4. Update cache
        console.log(`[CACHE] Caching answer details for question ${questionId}`);
        setAnswerDetailsCache(prevCache => ({
            ...prevCache,
            [questionId]: {
                correctAnswer: newCorrectAnswer,
                explanation: newExplanation,
                afterAnswerMedia: newAfterAnswerMedia,
                afterAnswerMediaType: newAfterAnswerMediaType,
            }
        }));

      }
    } catch (err) {
      console.error('[SECURITY] Error fetching secure correct answer:', err);
      
      if (err.response?.status === 403) {
        console.log('[SECURITY] Access denied for correct answer:', err.response.data.message);
      } else if (err.response?.status === 429) {
        console.log('[SECURITY] Rate limit exceeded for correct answer');
      }
    } finally {
      fetchCorrectAnswerSecure.isLoading = false;
      console.log('[CALL] fetchCorrectAnswerSecure end', { questionId });
    }
  };

  const handleAnswerSubmit = async (answerIndex) => {
    console.log('[ACTION] handleAnswerSubmit start', { answerIndex });
    if (answerSubmitted) {
      console.log('[ACTION] handleAnswerSubmit end - already submitted.');
      return;
    }
    
    // Prevent duplicate submissions
    if (handleAnswerSubmit.isSubmitting) {
      console.log('[DEBOUNCE] Skipping duplicate answer submission');
      console.log('[ACTION] handleAnswerSubmit end - submission in progress.');
      return;
    }
    
    handleAnswerSubmit.isSubmitting = true;
    setSelectedAnswer(answerIndex);
    setSyncing(true);
    
    const questionId = questions[currentQuestionIndex];
    const updatedAnswers = { ...userAnswers, [questionId]: answerIndex };
    
    setAnswerSubmitted(true);
    setUserAnswers(updatedAnswers);
    localStorage.setItem(`userAnswers_${lobbyId}`, JSON.stringify(updatedAnswers));
    
    try {
      console.log(`[SECURITY] Submitting secure answer for question ${questionId}:`, answerIndex);
      
      const response = await api.post(`/lobby_solo/${lobbyId}/secure/answer`, {
        question_id: questionId,
        answer_index: answerIndex,
        current_index: currentQuestionIndex,
        exam_mode: isExamMode,
        time_left: timeLeft
      });
      console.log(`[API] POST /lobby_solo/${lobbyId}/secure/answer`, response.data);
      
      if (response.data.status === "ok") {
        console.log('[SECURITY] Secure answer submitted successfully:', response.data);
        
        // Security: Only show answer if not in exam mode and access is granted
        const shouldShowAnswer = !isExamMode && response.data.data?.answer_access_granted;
        
        if (shouldShowAnswer) {
          try {
            console.log('[ACTION] handleAnswerSubmit -> calling fetchCorrectAnswerSecure');
            // Передаем обновленные ответы напрямую
            await fetchCorrectAnswerSecure(questionId, updatedAnswers);
          } catch (err) {
            console.warn("[SECURITY] Could not fetch secure correct answer", err);
          }
        } else if (isExamMode) {
          console.log('[SECURITY] Answer submitted in exam mode - correct answer will not be shown');
        }
      }
    } catch (err) {
      console.error('[SECURITY] Error submitting secure answer:', err);
      
      if (err.response?.status === 403) {
        console.log('[SECURITY] Answer submission denied:', err.response.data.message);
        showError('Доступ запрещен. Проверьте права доступа.');
      } else if (err.response?.status === 429) {
        console.log('[SECURITY] Rate limit exceeded for answer submission');
        showError('Слишком много попыток. Подождите немного.');
      } else if (err.response && !err.response.data?.message?.includes("не активен")) {
        showError(err.response?.data?.message || 'Failed to submit your answer');
      }
    } finally {
      setSyncing(false);
      handleAnswerSubmit.isSubmitting = false;
      console.log('[ACTION] handleAnswerSubmit end');
    }
  };

  // Fetch current question effect with debouncing
  useEffect(() => {
    console.log('[EFFECT] Trigger fetchCurrentQuestion.', { lobbyId, questions_length: questions.length, currentQuestionIndex, userAnswers_keys: Object.keys(userAnswers), isExamMode, testCompleted });
    if (testCompleted) return;
    
    const isLastQuestion = currentQuestionIndex === questions.length - 1;
    const currentQuestionId = questions[currentQuestionIndex];
    const isQuestionAnswered = userAnswers[currentQuestionId] !== undefined;
    
    if (isLastQuestion && isQuestionAnswered) {
      console.log("Last question is already answered");
      return;
    }
    
    // Debounce to prevent multiple rapid requests
    const timeoutId = setTimeout(() => {
      fetchCurrentQuestion().catch(err => {
        if (err.response?.status === 400 && 
            (err.response?.data?.message?.includes("не активен") || 
             err.response?.data?.message?.includes("не запущен"))) {
          console.log("Test status changed to inactive");
          if (isLastQuestion) {
            showError(null);
          }
        } else {
          console.error('Error fetching question:', err);
          showError(err.response?.data?.message || 'Failed to load question');
        }
      });
    }, 100); // 100ms debounce
    
    return () => clearTimeout(timeoutId);
  }, [lobbyId, questions, currentQuestionIndex, isExamMode, testCompleted]);

  const handleNextQuestion = () => {
    if (currentQuestionIndex < questions.length - 1) {
      // Reset loading states
      fetchCurrentQuestion.isLoading = false;
      fetchCorrectAnswerSecure.isLoading = false;
      
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    }
  };

  const handlePrevQuestion = () => {
    if (currentQuestionIndex > 0) {
      // Reset loading states
      fetchCurrentQuestion.isLoading = false;
      fetchCorrectAnswerSecure.isLoading = false;
      
      const newIndex = currentQuestionIndex - 1;
      setCurrentQuestionIndex(newIndex);
      setAnswerSubmitted(true); // Automatically show answer for previous questions
      setSelectedAnswer(userAnswers[questions[newIndex]]);
      setCorrectAnswer(null);
      setExplanation(null);
      setAfterAnswerMedia(null);
      setVideoError(false);
      setVideoProgress(0);
      
      // Fetch answer data for previous question
      const shouldShowAnswer = !isExamMode;
      if (shouldShowAnswer) {
        fetchCorrectAnswerSecure(questions[newIndex]);
      }
    }
  };

  const finishTestSecure = async () => {
    try {
      setSyncing(true);
      
      console.log('[SECURITY] Finishing test securely');
      
      // Sync final timer state if in exam mode
      if (isExamMode) {
        try {
          const currentTimeLeft = parseInt(localStorage.getItem(`exam_timer_${lobbyId}`) || '0', 10);
          await api.post(`/lobby_solo/${lobbyId}/secure/exam-timer`, {
            time_left: currentTimeLeft
          });
        } catch (err) {
          console.error('[SECURITY] Error syncing final secure timer state:', err);
        }
      }
      
      try {
        const response = await api.post(`/lobby_solo/${lobbyId}/secure/finish`, {
          final_answers: userAnswers,
          exam_mode: isExamMode,
          time_left: timeLeft
        });
        
        if (response.data.status === "ok") {
          console.log('[SECURITY] Test finished securely');
          setTestCompleted(true);
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
          }
          fetchTestResultsSecure();
        }
      } catch (err) {
        console.error('[SECURITY] Error finishing secure test:', err);
        
        if (err.response?.status === 400 && 
            (err.response?.data?.message?.includes("не активен") || 
             err.response?.data?.message?.includes("уже завершен"))) {
          console.log("[SECURITY] Test already finished securely");
          setTestCompleted(true);
          
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
          }
          
          fetchTestResultsSecure();
        } else {
          showError(err.response?.data?.message || 'Failed to finish test');
        }
      } finally {
        setSyncing(false);
      }
    } catch (e) {
      console.error('[SECURITY] Unexpected error in secure finishTest:', e);
      setSyncing(false);
      showError('An unexpected error occurred');
    }
  };

  const fetchTestResultsSecure = async () => {
    try {
      console.log('[SECURITY] Fetching secure test results');
      
      const response = await api.get(`/lobby_solo/${lobbyId}/secure/results`);
      
      if (response.data.status === "ok") {
        console.log('[SECURITY] Secure test results loaded');
        setTestResults(response.data.data);
        localStorage.removeItem(`exam_timer_${lobbyId}`);
        localStorage.removeItem(`userAnswers_${lobbyId}`);
        localStorage.removeItem(`currentQuestionIndex_${lobbyId}`);
      } else {
        showError(response.data.message || 'Failed to load test results');
      }
    } catch (err) {
      console.error('[SECURITY] Error fetching secure test results:', err);
      
      if (err.response?.status === 404 || 
          (err.response?.data?.message && err.response?.data?.message.includes("не активен"))) {
        setTestResults({
          user_result: {
            correct_count: 0,
            total_questions: questions.length,
            percentage: 0,
            passed: false
          }
        });
        
        localStorage.removeItem(`exam_timer_${lobbyId}`);
        localStorage.removeItem(`userAnswers_${lobbyId}`);
        localStorage.removeItem(`currentQuestionIndex_${lobbyId}`);
      } else {
        showError(err.response?.data?.message || 'Failed to load test results');
      }
    }
  };

  const finishTest = async () => {
    await finishTestSecure();
  };

  const fetchTestResults = async () => {
    await fetchTestResultsSecure();
  };

  // Format time
  const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds < 10 ? '0' : ''}${remainingSeconds}`;
  };

  const handleReturnToDashboard = () => {
    navigate('/dashboard');
  };

  // -------------------------------------------------------------
  // Helper: show error both in UI and notification system
  // -------------------------------------------------------------
  const showError = useCallback((msg) => {
    setError(msg);
    notify.error(msg, { important: true });
  }, []);

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

  // Test completed - show loading while redirecting
  if (testCompleted) {
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
            <div className="loading-text">Переход к результатам...</div>
          </div>
        </div>
      </div>
    );
  }

  // Active test
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
                <div className="nav-title">{getTranslation('questionNavigator')}</div>
                <div className="nav-subtitle">
                  {Object.keys(userAnswers).length}/{questions.length} {getTranslation('answered')}
                </div>
              </div>
              
              <div className="question-grid">
                {questions.map((questionId, index) => {
                  const isAnswered = userAnswers[questionId] !== undefined;
                  const isCurrent = index === currentQuestionIndex;
                  const isCorrect = !isExamMode && correctAnswer !== null && userAnswers[questionId] === correctAnswer?.index;
                  
                  let className = 'question-nav-item';
                  if (isCurrent) className += ' active';
                  if (isAnswered) {
                    if (isExamMode) {
                      className += ' answered-exam';
                    } else {
                      className += isCorrect ? ' answered' : ' incorrect';
                    }
                  }
                  
                  return (
                    <div 
                      key={questionId} 
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
                  
                  {/* Media Section - Always show container to prevent layout jumps */}
                  <div className="question-media">
                    <div className="media-container stable-container">
                      {mediaLoading ? (
                        <div className="loading-container" style={{ height: '100%', width: '100%' }}>
                          <div className="loading-bar-container">
                            <div className="loading-bar"></div>
                          </div>
                          <div className="loading-text">{getTranslation('loadingMedia')}</div>
                        </div>
                      ) : (
                        <QuestionMedia
                          currentQuestion={currentQuestion}
                          answerSubmitted={answerSubmitted}
                          isExamMode={isExamMode}
                          afterAnswerMedia={afterAnswerMedia}
                          afterAnswerMediaType={afterAnswerMediaType}
                          videoRef={videoRef}
                          afterVideoRef={afterVideoRef}
                          getTranslation={getTranslation}
                        />
                      )}
                    </div>
                  </div>
                  
                  {/* Answer Options */}
                  <div className="answer-options">
                    {currentQuestion.answers && currentQuestion.answers.map((answer, index) => {
                      const answerText = localizeText(answer);
                      
                      let answerClass = "answer-option";
                      if (answerSubmitted) {
                        if (isExamMode) {
                          // В экзаменационном режиме показываем только выбранный ответ без правильности
                          if (index === selectedAnswer) {
                            answerClass += " selected-exam";
                          }
                        } else {
                          // В обычном режиме показываем правильность ответов
                          if (index === selectedAnswer && index === correctAnswer?.index) {
                            answerClass += " correct";
                          } else if (index === selectedAnswer && index !== correctAnswer?.index) {
                            answerClass += " incorrect";
                          } else if (index === correctAnswer?.index) {
                            answerClass += " correct";
                          }
                        }
                      } else if (index === selectedAnswer) {
                        answerClass += " selected";
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
          
          {/* Navigation */}
          <div className="test-navigation">
            <button 
              className="nav-button prev"
              onClick={handlePrevQuestion}
              disabled={currentQuestionIndex === 0}
            >
              <FaArrowLeft />
              <span>{getTranslation('previousQuestion')}</span>
            </button>
            
            {currentQuestionIndex === questions.length - 1 ? (
              <button 
                className="nav-button finish"
                onClick={finishTest}
                disabled={!answerSubmitted}
              >
                <FaFlag />
                <span>{getTranslation('finishTest')}</span>
              </button>
            ) : (
              <button 
                className="nav-button next"
                onClick={handleNextQuestion}
                disabled={!answerSubmitted}
              >
                <span>{getTranslation('nextQuestion')}</span>
                <FaArrowRight />
              </button>
            )}
          </div>
        </div>
      </div>
      
      {/* Test Actions - Floating buttons */}
      <div className="test-actions">
        <button 
          className="action-button nav" 
          onClick={toggleQuestionNav}
          data-tooltip={getTranslation('questionNavigator')}
        >
          <FaBars />
          <span>{getTranslation('questionNavigator')}</span>
        </button>
        
        <button 
          className="action-button danger" 
          onClick={handleOpenReport}
          data-tooltip={getTranslation('reportQuestion')}
        >
          <FaExclamationTriangle />
          <span>{getTranslation('report')}</span>
        </button>
        
        <button 
          className="action-button danger" 
          onClick={() => {
            if (confirm(getTranslation('confirmFinishTest'))) {
              finishTest();
            }
          }}
          data-tooltip={getTranslation('finishEarly')}
        >
          <FaFlag />
          <span>{getTranslation('finishEarly')}</span>
        </button>
      </div>
      
      {/* Report Modal */}
      {showReportModal && (
        <div className="report-modal-overlay" onClick={handleCloseReport}>
          <div className="report-modal" onClick={(e) => e.stopPropagation()}>
            <div className="report-modal-header">
              <div className="report-modal-title">{getTranslation('reportQuestion')}</div>
              <div className="report-modal-subtitle">
                {getTranslation('question')} {currentQuestionIndex + 1}: {getTranslation('helpUsImprove')}
              </div>
            </div>
            
            <form className="report-form" onSubmit={handleSubmitReport}>
              <div className="form-group">
                <label className="form-label">{getTranslation('reportType')}</label>
                <select 
                  className="form-select"
                  value={reportData.type}
                  onChange={(e) => setReportData({...reportData, type: e.target.value})}
                  required
                >
                  <option value="">{getTranslation('selectReportType')}</option>
                  <option value="incorrect_answer">{getTranslation('incorrectAnswer')}</option>
                  <option value="unclear_question">{getTranslation('unclearQuestion')}</option>
                  <option value="technical_error">{getTranslation('technicalIssue')}</option>
                  <option value="inappropriate_content">{getTranslation('inappropriateContent')}</option>
                  <option value="other">{getTranslation('other')}</option>
                </select>
              </div>
              
              <div className="form-group">
                <label className="form-label">{getTranslation('description')}</label>
                <textarea 
                  className="form-textarea"
                  value={reportData.description}
                  onChange={(e) => setReportData({...reportData, description: e.target.value})}
                  placeholder={getTranslation('describeIssue')}
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
                  {getTranslation('cancel')}
                </button>
                <button 
                  type="submit" 
                  className="btn btn-danger"
                  disabled={reportSubmitting || !reportData.type || !reportData.description.trim()}
                >
                  {reportSubmitting ? getTranslation('submitting') : getTranslation('submitReport')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default TestPage; 