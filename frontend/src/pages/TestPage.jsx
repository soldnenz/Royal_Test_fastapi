import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  FaTimes, FaCheck, FaArrowLeft, FaArrowRight, FaFlag, 
  FaLanguage, FaMoon, FaSun, FaHistory, FaExclamationTriangle,
  FaPlay, FaPause, FaVolumeUp, FaVolumeMute, FaExpand,
  FaBars, FaQuestionCircle, FaLightbulb, FaClock, FaStar, FaChartBar, FaUser
} from 'react-icons/fa';
import api from '../utils/axios';
import DashboardHeader from '../components/dashboard/DashboardHeader';
import DashboardSidebar from '../components/dashboard/DashboardSidebar';
import { getCurrentTheme, toggleTheme, initTheme } from '../utils/themeUtil';
import { getCurrentLanguage, setLanguage, getTranslation, localizeText, LANGUAGES } from '../utils/languageUtil';
import './dashboard/styles.css';
import './TestPage.css';

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
  
  const intervalRef = useRef(null);
  const videoRef = useRef(null);
  const afterVideoRef = useRef(null);
  const videoIntervalRef = useRef(null);
  const videoProgressRef = useRef(null);
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
        const response = await api.get('/auth/profile');
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

  // Video progress tracking
  const updateVideoProgress = useCallback((video) => {
    if (!video || video.duration === 0) return;
    const progress = (video.currentTime / video.duration) * 100;
    setVideoProgress(progress);
  }, []);

  // Advanced video management with auto-loop and progress tracking
  const setupVideoAutoplay = useCallback((video) => {
    if (!video) return;

    // Clear any existing intervals
    if (videoIntervalRef.current) {
      clearInterval(videoIntervalRef.current);
    }
    if (videoProgressRef.current) {
      clearInterval(videoProgressRef.current);
    }

    // Set video properties
    video.muted = true;
    video.loop = false; // НЕ ЗАЦИКЛИВАЕМ автоматически
    video.currentTime = 1; // Start from 1 second
    setVideoLoading(true);

    // Show loading progress
    let loadProgress = 0;
    const loadInterval = setInterval(() => {
      loadProgress += 10;
      setVideoProgress(loadProgress);
      if (loadProgress >= 100) {
        clearInterval(loadInterval);
        setVideoLoading(false);
      }
    }, 100);

    // Start playing after 1 second delay
    setTimeout(() => {
      video.play().then(() => {
        setVideoLoading(false);
        clearInterval(loadInterval);
        
        // Запустить повтор через 10 секунд после окончания видео
        const handleVideoEnd = () => {
          setTimeout(() => {
            if (video && !video.paused && video.readyState >= 3) {
              video.currentTime = 1;
              video.play().catch(console.log);
            }
          }, 10000); // 10 секунд после окончания
        };
        
        video.addEventListener('ended', handleVideoEnd);
        
        // Cleanup для ended listener
        return () => {
          video.removeEventListener('ended', handleVideoEnd);
        };
      }).catch(console.log);
    }, 1000);

    // Track video progress
    videoProgressRef.current = setInterval(() => {
      updateVideoProgress(video);
    }, 100);

    // Handle click to restart
    const handleVideoClick = () => {
      video.currentTime = 1;
      video.play().catch(console.log);
    };

    video.addEventListener('click', handleVideoClick);

    // Cleanup function
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
      await api.post(`/lobbies/lobbies/${lobbyId}/report`, {
        question_id: questions[currentQuestionIndex],
        report_type: reportData.type,
        description: reportData.description
      });
      
      // Show success message
      alert(getTranslation('reportSubmittedSuccessfully') || 'Report submitted successfully');
      handleCloseReport();
    } catch (err) {
      console.error('Error submitting report:', err);
      alert(getTranslation('reportSubmissionFailed') || 'Failed to submit report. Please try again.');
    } finally {
      setReportSubmitting(false);
    }
  };

  // Fetch lobby information
  useEffect(() => {
    const fetchLobbyInfo = async () => {
      try {
        console.log(`Fetching lobby info for ID: ${lobbyId}`);
        setSyncing(true);
        const response = await api.get(`/lobbies/lobbies/${lobbyId}`);
        
        if (response.data.status === "ok") {
          console.log("Lobby info loaded successfully:", response.data.data);
          setLobbyInfo(response.data.data);
          
          if (response.data.data.status === 'completed' || response.data.data.status === 'inactive') {
            setTestCompleted(true);
            fetchTestResults();
            return;
          }
          
          setIsExamMode(response.data.data.exam_mode === true);
          
          if (response.data.data.question_ids && response.data.data.question_ids.length > 0) {
            setQuestions(response.data.data.question_ids);
            
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
          setError(response.data.message || 'Failed to load test information');
        }
        
        setLoading(false);
        setSyncing(false);
      } catch (err) {
        console.error('Error fetching lobby info:', err);
        setError(err.response?.data?.message || 'Failed to load test information');
        setLoading(false);
        setSyncing(false);
      }
    };

    fetchLobbyInfo();
  }, [lobbyId]);

  // Fetch current question
  const fetchCurrentQuestion = async () => {
    if (!questions.length || currentQuestionIndex >= questions.length) return;
    
    const questionId = questions[currentQuestionIndex];
    
    try {
      setMediaLoading(true);
      setVideoError(false);
      
      const response = await api.get(`/lobbies/lobbies/${lobbyId}/questions/${questionId}`);
      
      if (response.data.status === "ok") {
        const questionData = response.data.data;
        
        if (questionData.has_media) {
          const mediaUrl = `/api/lobbies/files/media/${questionId}?t=${Date.now()}`;
          questionData.media_url = mediaUrl;
        }
        
        setCurrentQuestion(questionData);
        setAnswerSubmitted(false);
        setSelectedAnswer(null);
        setCorrectAnswer(null);
        setExplanation(null);
        setAfterAnswerMedia(null);
        
        if (userAnswers[questionId] !== undefined) {
          setSelectedAnswer(userAnswers[questionId]);
          setAnswerSubmitted(true);
          
          if (!isExamMode) {
            fetchCorrectAnswer(questionId);
          }
        }
        
        setMediaLoading(false);
      } else {
        setError(response.data.message || 'Failed to load question');
        setMediaLoading(false);
      }
    } catch (err) {
      console.error('Error fetching question:', err);
      setError(err.response?.data?.message || 'Failed to load question');
      setMediaLoading(false);
    }
  };

  // Save user answers to localStorage
  useEffect(() => {
    if (Object.keys(userAnswers).length > 0) {
      localStorage.setItem(`userAnswers_${lobbyId}`, JSON.stringify(userAnswers));
    }
  }, [userAnswers, lobbyId]);

  // Timer for exam mode
  useEffect(() => {
    if (isExamMode && !testCompleted) {
      const savedTimeLeft = localStorage.getItem(`exam_timer_${lobbyId}`);
      if (savedTimeLeft) {
        setTimeLeft(parseInt(savedTimeLeft, 10));
      }

      intervalRef.current = setInterval(() => {
        setTimeLeft(prevTime => {
          const newTime = prevTime <= 1 ? 0 : prevTime - 1;
          localStorage.setItem(`exam_timer_${lobbyId}`, newTime.toString());
          
          if (newTime <= 0) {
            clearInterval(intervalRef.current);
            finishTest();
            return 0;
          }
          return newTime;
        });
      }, 1000);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isExamMode, testCompleted, lobbyId]);

  const fetchCorrectAnswer = async (questionId) => {
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
  };

  const fetchAfterAnswerMedia = async (questionId) => {
    try {
      setMediaLoading(true);
      const mediaUrl = `/api/lobbies/files/after-answer-media/${questionId}?t=${Date.now()}`;
      setAfterAnswerMedia(mediaUrl);
      setMediaLoading(false);
    } catch (err) {
      console.error('Error fetching after-answer media:', err);
      setMediaLoading(false);
    }
  };

  const handleAnswerSubmit = async (answerIndex) => {
    if (answerSubmitted) return;
    
    setSelectedAnswer(answerIndex);
    setSyncing(true);
    
    const questionId = questions[currentQuestionIndex];
    const updatedAnswers = { ...userAnswers, [questionId]: answerIndex };
    
    setAnswerSubmitted(true);
    setUserAnswers(updatedAnswers);
    localStorage.setItem(`userAnswers_${lobbyId}`, JSON.stringify(updatedAnswers));
    
    try {
      const response = await api.post(`/lobbies/lobbies/${lobbyId}/answer`, {
        question_id: questionId,
        answer_index: answerIndex
      });
      
      if (response.data.status === "ok") {
        if (!isExamMode) {
          try {
            await fetchCorrectAnswer(questionId);
          } catch (err) {
            console.warn("Could not fetch correct answer", err);
          }
        }
      }
    } catch (err) {
      console.error('Error submitting answer:', err);
      if (err.response && !err.response.data?.message?.includes("не активен")) {
        setError(err.response?.data?.message || 'Failed to submit your answer');
      }
    } finally {
      setSyncing(false);
    }
  };

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
        setError(err.response?.data?.message || 'Failed to load question');
      }
    });
  }, [lobbyId, questions, currentQuestionIndex, userAnswers, isExamMode, testCompleted]);

  const handleNextQuestion = () => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    }
  };

  const handlePrevQuestion = () => {
    if (currentQuestionIndex > 0) {
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
      if (!isExamMode) {
        fetchCorrectAnswer(questions[newIndex]);
      }
    }
  };

  const finishTest = async () => {
    try {
      setSyncing(true);
      
      try {
        const response = await api.post(`/lobbies/lobbies/${lobbyId}/finish`, {});
        
        if (response.data.status === "ok") {
          setTestCompleted(true);
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
          }
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
          setError(err.response?.data?.message || 'Failed to finish test');
        }
      } finally {
        setSyncing(false);
      }
    } catch (e) {
      console.error('Unexpected error in finishTest:', e);
      setSyncing(false);
      setError('An unexpected error occurred');
    }
  };

  const fetchTestResults = async () => {
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
        setError(err.response?.data?.message || 'Failed to load test results');
      }
    }
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

  // Test results
  if (testCompleted && testResults) {
    const percentage = testResults.user_result.percentage;
    const correctCount = testResults.user_result.correct_count;
    const totalQuestions = testResults.user_result.total_questions;
    const incorrectCount = totalQuestions - correctCount;
    const isPassed = testResults.user_result.passed || percentage >= 70;
    
    // Calculate additional metrics
    const totalTimeSpent = 40 * 60 - timeLeft; // in seconds
    const averageTimePerQuestion = Math.round(totalTimeSpent / totalQuestions);
    const efficiency = Math.round((correctCount / totalQuestions) * 100);
    
    // Determine skill level
    let skillLevel = '';
    let skillColor = '';
    if (percentage >= 95) { 
      skillLevel = getTranslation('excellent'); 
      skillColor = 'var(--success)';
    } else if (percentage >= 85) { 
      skillLevel = getTranslation('veryGood'); 
      skillColor = 'var(--success)';
    } else if (percentage >= 75) { 
      skillLevel = getTranslation('good'); 
      skillColor = 'var(--warning)';
    } else if (percentage >= 65) { 
      skillLevel = getTranslation('satisfactory'); 
      skillColor = 'var(--warning)';
    } else if (percentage >= 50) { 
      skillLevel = getTranslation('needsImprovement'); 
      skillColor = 'var(--error)';
    } else { 
      skillLevel = getTranslation('poor'); 
      skillColor = 'var(--error)';
    }
    
    const formatTime = (seconds) => {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const secs = seconds % 60;
      if (hours > 0) {
        return `${hours}:${minutes < 10 ? '0' : ''}${minutes}:${secs < 10 ? '0' : ''}${secs}`;
      }
      return `${minutes}:${secs < 10 ? '0' : ''}${secs}`;
    };
    
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
            {/* Results Header */}
            <div className="results-header">
              <div className={`results-icon ${isPassed ? 'success' : 'failed'}`}>
                {isPassed ? <FaStar size={48} /> : <FaTimes size={48} />}
              </div>
              
              <div className="results-title-section">
                <h1 className="results-title">{getTranslation('testResults')}</h1>
                <div className={`results-status ${isPassed ? 'passed' : 'failed'}`}>
                  {isPassed ? getTranslation('passed') : getTranslation('failed')}
                </div>
              </div>
              
              <div className="results-score-circle">
                <div className="score-percentage" style={{ color: skillColor }}>
                  {percentage}%
                </div>
                <div className="score-description">
                  {getTranslation('yourScore')}
                </div>
              </div>
            </div>
            
            {/* Main Results Grid */}
            <div className="results-grid">
              {/* Score Overview Card */}
              <div className="result-card score-overview">
                <div className="card-header">
                  <FaStar className="card-icon" />
                  <h3>{getTranslation('overallPerformance')}</h3>
                </div>
                <div className="card-content">
                  <div className="score-display">
                    <div className="main-score" style={{ color: skillColor }}>
                      {percentage}%
                    </div>
                    <div className="score-fraction">
                      {correctCount} / {totalQuestions}
                    </div>
                    <div className="skill-level" style={{ color: skillColor }}>
                      {skillLevel}
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Detailed Statistics Card */}
              <div className="result-card detailed-stats">
                <div className="card-header">
                  <FaChartBar className="card-icon" />
                  <h3>{getTranslation('detailedAnalysis')}</h3>
                </div>
                <div className="card-content">
                  <div className="stats-grid">
                    <div className="stat-item">
                      <span className="stat-label">{getTranslation('questionsCorrect')}</span>
                      <span className="stat-value correct">{correctCount}</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-label">{getTranslation('questionsIncorrect')}</span>
                      <span className="stat-value incorrect">{incorrectCount}</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-label">{getTranslation('totalQuestions')}</span>
                      <span className="stat-value total">{totalQuestions}</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-label">{getTranslation('accuracy')}</span>
                      <span className="stat-value">{percentage}%</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-label">{getTranslation('efficiency')}</span>
                      <span className="stat-value">{efficiency}%</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-label">{getTranslation('completionRate')}</span>
                      <span className="stat-value">100%</span>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Time Analysis Card */}
              <div className="result-card time-analysis">
                <div className="card-header">
                  <FaClock className="card-icon" />
                  <h3>{getTranslation('timeAnalysis')}</h3>
                </div>
                <div className="card-content">
                  <div className="time-stats">
                    <div className="time-item">
                      <span className="time-label">{getTranslation('timeSpent')}</span>
                      <span className="time-value">{formatTime(totalTimeSpent)}</span>
                    </div>
                    <div className="time-item">
                      <span className="time-label">{getTranslation('averageTimePerQuestion')}</span>
                      <span className="time-value">{averageTimePerQuestion}s</span>
                    </div>
                    {isExamMode && (
                      <div className="time-item">
                        <span className="time-label">{getTranslation('timeRemaining')}</span>
                        <span className="time-value">{formatTime(timeLeft)}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
              
              {/* Session Information Card */}
              <div className="result-card session-info">
                <div className="card-header">
                  <FaUser className="card-icon" />
                  <h3>{getTranslation('sessionInfo')}</h3>
                </div>
                <div className="card-content">
                  <div className="session-stats">
                    <div className="session-item">
                      <span className="session-label">{getTranslation('testType')}</span>
                      <span className="session-value">{isExamMode ? getTranslation('expert') : getTranslation('practice')}</span>
                    </div>
                    <div className="session-item">
                      <span className="session-label">{getTranslation('testDate')}</span>
                      <span className="session-value">{new Date().toLocaleDateString()}</span>
                    </div>
                    <div className="session-item">
                      <span className="session-label">{getTranslation('passingScore')}</span>
                      <span className="session-value">70%</span>
                    </div>
                    <div className="session-item">
                      <span className="session-label">{getTranslation('difficulty')}</span>
                      <span className="session-value">{getTranslation('medium')}</span>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Performance Insights Card */}
              <div className="result-card performance-insights">
                <div className="card-header">
                  <FaLightbulb className="card-icon" />
                  <h3>{getTranslation('recommendation')}</h3>
                </div>
                <div className="card-content">
                  <div className="insights">
                    {isPassed ? (
                      <>
                        <div className="insight-item success">
                          <FaCheck className="insight-icon" />
                          <span>{getTranslation('congratulationsYouPassed')}</span>
                        </div>
                        {percentage >= 95 && (
                          <div className="insight-item">
                            <FaStar className="insight-icon" />
                            <span>{getTranslation('excellent')} {getTranslation('performance')}!</span>
                          </div>
                        )}
                      </>
                    ) : (
                      <>
                        <div className="insight-item warning">
                          <FaTimes className="insight-icon" />
                          <span>{getTranslation('testNotPassed')}</span>
                        </div>
                        <div className="insight-item">
                          <FaHistory className="insight-icon" />
                          <span>{getTranslation('retakeAdvice')}</span>
                        </div>
                      </>
                    )}
                    
                    {incorrectCount > 0 && (
                      <div className="insight-item">
                        <FaExclamationTriangle className="insight-icon" />
                        <span>{getTranslation('improvementAreas')}: {incorrectCount} {getTranslation('questionsIncorrect')}</span>
                      </div>
                    )}
                    
                    <div className="insight-item">
                      <FaClock className="insight-icon" />
                      <span>{getTranslation('averageTimePerQuestion')}: {averageTimePerQuestion}s</span>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Summary Card - Full Width */}
              <div className="result-card summary-card full-width">
                <div className="card-header">
                  <FaChartBar className="card-icon" />
                  <h3>{getTranslation('summary')}</h3>
                </div>
                <div className="card-content">
                  <div className="summary-content">
                    <div className="summary-text">
                      {isPassed ? (
                        <p style={{ color: 'var(--success)', fontWeight: '600' }}>
                          🎉 {getTranslation('congratulationsYouPassed')} 
                          {percentage >= 95 && " " + getTranslation('excellent') + " " + getTranslation('performance') + "!"}
                        </p>
                      ) : (
                        <p style={{ color: 'var(--error)', fontWeight: '600' }}>
                          📚 {getTranslation('testNotPassed')} {getTranslation('nextSteps')}: {getTranslation('studyRecommendations')}
                        </p>
                      )}
                      
                      <div className="final-breakdown">
                        <span className="breakdown-item">
                          ✅ {correctCount} {getTranslation('questionsCorrect')}
                        </span>
                        <span className="breakdown-item">
                          ❌ {incorrectCount} {getTranslation('questionsIncorrect')}
                        </span>
                        <span className="breakdown-item">
                          ⏱️ {formatTime(totalTimeSpent)} {getTranslation('timeSpent')}
                        </span>
                        <span className="breakdown-item">
                          🎯 {percentage}% {getTranslation('accuracy')}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Action Button */}
            <div className="results-actions">
              <button className="btn btn-large btn-primary" onClick={handleReturnToDashboard}>
                <FaStar />
                {getTranslation('returnToDashboard')}
              </button>
            </div>
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
                  const isCorrect = !isExamMode && correctAnswer !== null && userAnswers[questionId] === correctAnswer;
                  
                  let className = 'question-nav-item';
                  if (isCurrent) className += ' active';
                  if (isAnswered) {
                    if (isExamMode) {
                      className += ' answered';
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
                      {/* Show after-answer media if available and answered */}
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
                              {/* Video Progress Bar */}
                              <div className={`video-progress-container ${videoLoading ? 'loading' : ''}`}>
                                <div className="video-progress-bar">
                                  <div 
                                    className={videoLoading ? "video-loading-bar" : "video-progress"}
                                    style={{ width: `${videoProgress}%` }}
                                  ></div>
                                </div>
                              </div>
                            </div>
                          </div>
                        ) : (
                          <img 
                            src={afterAnswerMedia}
                            alt="Explanation"
                            className="question-image"
                            onError={(e) => {
                              e.target.style.display = 'none';
                            }}
                          />
                        )
                      ) : (
                        // Show main media
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
                                  {/* Video Progress Bar */}
                                  <div className={`video-progress-container ${videoLoading ? 'loading' : ''}`}>
                                    <div className="video-progress-bar">
                                      <div 
                                        className={videoLoading ? "video-loading-bar" : "video-progress"}
                                        style={{ width: `${videoProgress}%` }}
                                      ></div>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            )
                          ) : (
                            <img 
                              src={currentQuestion.media_url}
                              alt="Question"
                              className="question-image"
                              onError={(e) => {
                                e.target.style.display = 'none';
                              }}
                            />
                          )
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
                        if (index === selectedAnswer && (!isExamMode && index === correctAnswer)) {
                          answerClass += " correct";
                        } else if (index === selectedAnswer && (!isExamMode && index !== correctAnswer)) {
                          answerClass += " incorrect";
                        } else if (!isExamMode && index === correctAnswer) {
                          answerClass += " correct";
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
                  <option value="technical_issue">{getTranslation('technicalIssue')}</option>
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