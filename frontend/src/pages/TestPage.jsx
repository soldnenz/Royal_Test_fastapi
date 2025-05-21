import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FaTimes, FaCheck, FaArrowLeft, FaArrowRight, FaFlag, FaLanguage, FaMoon, FaSun, FaHistory } from 'react-icons/fa';
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
    // Try to retrieve the last question index from localStorage
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
  const [timeLeft, setTimeLeft] = useState(40 * 60); // 40 minutes in seconds
  const [mediaLoading, setMediaLoading] = useState(false);
  const [mediaProgress, setMediaProgress] = useState(0);
  const [isExamMode, setIsExamMode] = useState(false);
  const [testCompleted, setTestCompleted] = useState(false);
  const [testResults, setTestResults] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isHistorySidebarOpen, setIsHistorySidebarOpen] = useState(false);
  const [profileData, setProfileData] = useState(null);
  const [videoError, setVideoError] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const intervalRef = useRef(null);
  const isDarkTheme = theme === 'dark';
  const [videoBlobUrl, setVideoBlobUrl] = useState(null);
  const videoFetchController = useRef(null);
  // Флаг, показывающий, нужно ли отображать медиа-объяснение внизу
  const [showExtraMedia, setShowExtraMedia] = useState(false);

  // Initialize theme when component mounts
  useEffect(() => {
    initTheme();
    // Set up initial theme class on body
    document.body.classList.toggle('dark-theme', theme === 'dark');
  }, []);

  // Handle theme changes from other components
  useEffect(() => {
    const handleThemeChange = () => {
      const newTheme = getCurrentTheme();
      setTheme(newTheme);
      document.body.classList.toggle('dark-theme', newTheme === 'dark');
    };
    
    window.addEventListener('themeChange', handleThemeChange);
    return () => {
      window.removeEventListener('themeChange', handleThemeChange);
    };
  }, []);

  // Handle language changes from other components
  useEffect(() => {
    const handleLanguageChange = () => {
      setCurrentLanguage(getCurrentLanguage());
    };
    
    window.addEventListener('languageChange', handleLanguageChange);
    return () => {
      window.removeEventListener('languageChange', handleLanguageChange);
    };
  }, []);

  // Save current question index when it changes
  useEffect(() => {
    localStorage.setItem(`currentQuestionIndex_${lobbyId}`, currentQuestionIndex.toString());
  }, [currentQuestionIndex, lobbyId]);

  // Handle theme toggle
  const handleToggleTheme = () => {
    const newTheme = toggleTheme();
    setTheme(newTheme);
    document.body.classList.toggle('dark-theme', newTheme === 'dark');
  };

  // Handle language change
  const handleChangeLanguage = (newLanguage) => {
    if (setLanguage(newLanguage)) {
      setCurrentLanguage(newLanguage);
      // Dispatch an event to notify other components
      window.dispatchEvent(new Event('languageChange'));
    }
  };

  useEffect(() => {
    // Load user profile data
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

  // Toggle sidebar
  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  // Toggle history sidebar
  const toggleHistorySidebar = () => {
    setIsHistorySidebarOpen(!isHistorySidebarOpen);
  };

  // Fetch lobby info
  useEffect(() => {
    const fetchLobbyInfo = async () => {
      try {
        console.log(`Fetching lobby info for ID: ${lobbyId}`);
        setSyncing(true);
        const response = await api.get(`/lobbies/lobbies/${lobbyId}`);
        
        if (response.data.status === "ok") {
          console.log("Lobby info loaded successfully:", response.data.data);
          setLobbyInfo(response.data.data);
          
          // Check if the test is already completed
          if (response.data.data.status === 'completed' || response.data.data.status === 'inactive') {
            setTestCompleted(true);
            fetchTestResults();
            return; // Exit early if test is already completed
          }
          
          // Check if exam mode is enabled
          setIsExamMode(response.data.data.exam_mode === true);
          
          // Initialize question IDs
          if (response.data.data.question_ids && response.data.data.question_ids.length > 0) {
            setQuestions(response.data.data.question_ids);
            
            // Sync server state with local storage
            // Get server answers for comparison
            const serverAnswers = response.data.data.user_answers || {};
            
            // Load saved answers from localStorage if they exist
            let localAnswers = {};
            const savedAnswers = localStorage.getItem(`userAnswers_${lobbyId}`);
            if (savedAnswers) {
              try {
                localAnswers = JSON.parse(savedAnswers);
                console.log("Loaded saved answers from localStorage:", localAnswers);
              } catch (e) {
                console.error("Error parsing saved answers:", e);
              }
            }
            
            // Merge server and local answers, with server taking precedence
            const mergedAnswers = { ...localAnswers, ...serverAnswers };
            
            // Update state and localStorage with merged answers
            if (Object.keys(mergedAnswers).length > 0) {
              setUserAnswers(mergedAnswers);
              localStorage.setItem(`userAnswers_${lobbyId}`, JSON.stringify(mergedAnswers));
              console.log("Merged answers (server + local):", mergedAnswers);
              
              // Determine current question index based on answered questions
              const answeredQuestionIds = Object.keys(mergedAnswers);
              if (answeredQuestionIds.length > 0) {
                const lastAnsweredId = answeredQuestionIds[answeredQuestionIds.length - 1];
                const lastAnsweredIndex = response.data.data.question_ids.indexOf(lastAnsweredId);
                
                // Set to the next unanswered question or the last question if all are answered
                const nextIndex = Math.min(lastAnsweredIndex + 1, response.data.data.question_ids.length - 1);
                setCurrentQuestionIndex(nextIndex);
                localStorage.setItem(`currentQuestionIndex_${lobbyId}`, nextIndex.toString());
              }
            }
          }
        } else {
          console.error('Error in lobby info response:', response.data);
          setError(response.data.message || 'Failed to load test information');
        }
        
        setLoading(false);
        setSyncing(false);
      } catch (err) {
        console.error('Error fetching lobby info:', err);
        console.error('Error response data:', err.response?.data);
        setError(err.response?.data?.message || 'Failed to load test information');
        setLoading(false);
        setSyncing(false);
      }
    };

    fetchLobbyInfo();
  }, [lobbyId]);

  // Add function to fetch video as blob
  const fetchVideoAsBlob = async (url) => {
    try {
      // Cancel any existing fetch
      if (videoFetchController.current) {
        videoFetchController.current.abort();
      }
      
      // Create new controller for this fetch
      videoFetchController.current = new AbortController();
      
      console.log("Fetching video as blob:", url);
      setMediaLoading(true);
      
      const response = await fetch(url, {
        signal: videoFetchController.current.signal
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const blob = await response.blob();
      console.log("Video blob received:", blob.size, "bytes, type:", blob.type);
      
      // Create a blob URL
      const blobUrl = URL.createObjectURL(blob);
      console.log("Blob URL created:", blobUrl);
      
      setVideoBlobUrl(blobUrl);
      setMediaLoading(false);
      setVideoError(false);
      
      return blobUrl;
    } catch (err) {
      if (err.name === 'AbortError') {
        console.log("Video fetch aborted");
      } else {
        console.error("Error fetching video blob:", err);
        setVideoError(true);
      }
      setMediaLoading(false);
      return null;
    }
  };

  // Add cleanup for blob URLs
  useEffect(() => {
    return () => {
      if (videoBlobUrl) {
        URL.revokeObjectURL(videoBlobUrl);
      }
    };
  }, [videoBlobUrl]);

  // Update the fetchCurrentQuestion function to handle media
  const fetchCurrentQuestion = async () => {
    if (!questions.length || currentQuestionIndex >= questions.length) return;
    
    const questionId = questions[currentQuestionIndex];
    
    try {
      setMediaLoading(true);
      setMediaProgress(0);
      setVideoError(false);
      
      console.log(`Fetching question ${questionId} for lobby ${lobbyId}`);
      const response = await api.get(`/lobbies/lobbies/${lobbyId}/questions/${questionId}`, {
        onDownloadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            setMediaProgress(percentCompleted);
          }
        }
      });
      
      console.log(`Question data:`, response.data.data);
      
      if (response.data.status === "ok") {
        // Get the question data
        const questionData = response.data.data;
        
        // Debug the media type
        console.log(`Question media type from API: ${questionData.media_type}`);
        
        // Add media URL directly if has_media is true - WITHOUT timestamp to enable caching
        if (questionData.has_media) {
          const mediaUrl = `/api/lobbies/files/media/${questionId}`;
          questionData.media_url = mediaUrl;
          console.log(`Setting direct media URL: ${mediaUrl}`);
          
          // If it's a video, start fetching it as a blob
          if (questionData.media_type === 'video') {
            console.log("Video item detected - will fetch as blob");
            fetchVideoAsBlob(mediaUrl);
          }
        }
        
        // Store the question with media URL already set
        setCurrentQuestion(questionData);
        setAnswerSubmitted(false);
        setSelectedAnswer(null);
        setCorrectAnswer(null);
        setExplanation(null);
        setAfterAnswerMedia(null);
        
        // Check if user has already answered this question
        if (userAnswers[questionId] !== undefined) {
          setSelectedAnswer(userAnswers[questionId]);
          setAnswerSubmitted(true);
          
          // If not in exam mode, also get the correct answer and explanation
          if (!isExamMode) {
            fetchCorrectAnswer(questionId);
          }
        }
        
        // For videos, check if testing is needed (only do visual verification, don't actually fetch)
        if (questionData.has_media && questionData.media_type === 'video') {
          console.log("Video item detected - will be loaded by video element directly");
        }
        
        setMediaLoading(false);
      } else {
        console.error('Error in question response:', response.data);
        setError(response.data.message || 'Failed to load question');
        setMediaLoading(false);
      }
    } catch (err) {
      console.error('Error fetching question:', err);
      setError(err.response?.data?.message || 'Failed to load question');
      setMediaLoading(false);
    }
  };

  // Save user answers to localStorage whenever they change
  useEffect(() => {
    if (Object.keys(userAnswers).length > 0) {
      localStorage.setItem(`userAnswers_${lobbyId}`, JSON.stringify(userAnswers));
    }
  }, [userAnswers, lobbyId]);

  // Setup timer for exam mode
  useEffect(() => {
    if (isExamMode && !testCompleted) {
      // Try to retrieve saved time from localStorage first
      const savedTimeLeft = localStorage.getItem(`exam_timer_${lobbyId}`);
      if (savedTimeLeft) {
        setTimeLeft(parseInt(savedTimeLeft, 10));
      }

      intervalRef.current = setInterval(() => {
        setTimeLeft(prevTime => {
          const newTime = prevTime <= 1 ? 0 : prevTime - 1;
          
          // Save the current time to localStorage
          localStorage.setItem(`exam_timer_${lobbyId}`, newTime.toString());
          
          if (newTime <= 0) {
            // Time's up, finish the test
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
        
        // Fetch after-answer media if available
        if (response.data.data.has_after_media) {
          fetchAfterAnswerMedia(questionId);
        }
      } else {
        console.error('Error in correct answer response:', response.data);
      }
    } catch (err) {
      console.error('Error fetching correct answer:', err);
    }
  };

  // Improve the fetchAfterAnswerMedia function
  const fetchAfterAnswerMedia = async (questionId) => {
    try {
      setMediaLoading(true);
      setMediaProgress(0);
      
      // Create direct URL to the after-answer media WITHOUT timestamp
      const mediaUrl = `/api/lobbies/files/after-answer-media/${questionId}`;
      
      // Use the after_answer_media_type from current question data if available
      if (currentQuestion) {
        // Этот флаг указывает, что у вопроса есть видео/изображение после ответа
        // которое должно заменить основное медиа
        const updatedQuestion = {
          ...currentQuestion,
          has_after_answer_media: true,
          after_answer_media_type: currentQuestion.after_answer_media_type || currentQuestion.media_type
        };
        setCurrentQuestion(updatedQuestion);
        
        // Если это видео, загрузить его как blob для лучшей совместимости
        if (updatedQuestion.after_answer_media_type === 'video') {
          console.log("After-answer video detected - will fetch as blob to replace main video");
          try {
            const blob = await fetch(mediaUrl).then(r => r.blob());
            if (blob) {
              // Освободить предыдущий blob URL перед созданием нового
              if (videoBlobUrl) {
                URL.revokeObjectURL(videoBlobUrl);
              }
              const newBlobUrl = URL.createObjectURL(blob);
              console.log("Created blob URL for after-answer video:", newBlobUrl);
              setVideoBlobUrl(newBlobUrl);
            }
          } catch (err) {
            console.error("Error fetching after-answer video as blob:", err);
          }
        }
      }
      
      // Set the media URL directly
      setAfterAnswerMedia(mediaUrl);
      setMediaLoading(false);
    } catch (err) {
      console.error('Error fetching after-answer media:', err);
      setMediaLoading(false);
    }
  };

  // Update the handleAnswerSubmit function to better handle test completion
  const handleAnswerSubmit = async (answerIndex) => {
    if (answerSubmitted) return;
    
    setSelectedAnswer(answerIndex);
    setSyncing(true);
    
    // First, update local state immediately for better UX
    const questionId = questions[currentQuestionIndex];
    const isLastQuestion = currentQuestionIndex === questions.length - 1;
    
    // Create updated answers object
    const updatedAnswers = {
      ...userAnswers,
      [questionId]: answerIndex
    };
    
    // Mark answer as submitted in local state
    setAnswerSubmitted(true);
    setUserAnswers(updatedAnswers);
    
    // Save to localStorage regardless of server response
    localStorage.setItem(`userAnswers_${lobbyId}`, JSON.stringify(updatedAnswers));
    
    try {
      const response = await api.post(`/lobbies/lobbies/${lobbyId}/answer`, {
        question_id: questionId,
        answer_index: answerIndex
      });
      
      if (response.data.status === "ok") {
        // If not in exam mode, fetch the correct answer and explanation
        if (!isExamMode) {
          try {
            await fetchCorrectAnswer(questionId);
          } catch (err) {
            console.warn("Could not fetch correct answer, likely because test is no longer active", err);
            // Don't show error to user, we already saved the answer locally
          }
        }
        
        // Check if this is the last question and all questions are answered
        const allAnswered = questions.every(qId => updatedAnswers[qId] !== undefined);
        
        if (isLastQuestion && allAnswered) {
          console.log("This is the last question and all are answered. User should click Finish Test button.");
        }
      } else {
        console.error('Error in answer submission response:', response.data);
        // Don't show error on last question - we've already updated local state
        if (!isLastQuestion) {
          setError(response.data.message || 'Failed to submit your answer');
        }
      }
    } catch (err) {
      console.error('Error submitting answer:', err);
      
      // Check if it's the "Test not active" error
      if (err.response && (
          err.response.data?.message?.includes("не активен") ||
          err.response.data?.message?.includes("not active") ||
          err.response.data?.message?.includes("должен быть 'in_progress'")
      )) {
        console.log("Test is inactive but answer was saved locally");
        // Clear any error so user doesn't see it
        setError(null);
        
        // If not in exam mode and this happens on the last question, try to show the explanation anyway
        if (!isExamMode && isLastQuestion) {
          try {
            // We'll just use a local explanation since we can't fetch from server
            setCorrectAnswer(null); // We don't know what's correct
            setExplanation({
              ru: "Пояснение недоступно. Тест уже завершен.",
              en: "Explanation unavailable. The test has already been completed."
            });
          } catch (e) {
            console.error("Could not set local explanation:", e);
          }
        }
      }
      // Other errors are already handled by the local state update
      else if (err.response) {
        // Only show errors for non-last questions
        if (!isLastQuestion) {
          setError(err.response?.data?.message || 'Failed to submit your answer');
        }
      }
    } finally {
      setSyncing(false);
    }
  };

  // Update useEffect for fetchCurrentQuestion
  useEffect(() => {
    if (testCompleted) {
      // Don't fetch questions if test is already completed
      return;
    }
    
    // Skip question fetch for the last question when already answered
    // This prevents "Test not active" errors when answering the last question
    const isLastQuestion = currentQuestionIndex === questions.length - 1;
    const currentQuestionId = questions[currentQuestionIndex];
    const isQuestionAnswered = userAnswers[currentQuestionId] !== undefined;
    
    if (isLastQuestion && isQuestionAnswered) {
      console.log("Last question is already answered - skipping question fetch to prevent 'Test not active' errors");
      return;
    }
    
    fetchCurrentQuestion().catch(err => {
      // Special handling for "Test not active" errors after answering the last question
      if (err.response?.status === 400 && 
          (err.response?.data?.message?.includes("не активен") || 
           err.response?.data?.message?.includes("не запущен") ||
           err.response?.data?.message?.includes("должен быть 'in_progress'"))) {
        console.log("Test status changed to inactive after answering the last question");
        // Don't show an error, just show the final screen with the finish button
        
        // Update UI to show completion message but don't auto-finish
        if (isLastQuestion) {
          // Clear any error message that might be showing
          setError(null);
          console.log("Last question answered. Please click 'Finish Test' button to see results.");
          // Don't set testCompleted = true, let user click the button
        } else {
          console.error("Test became inactive but not all questions are answered");
        }
      } else {
        // For other errors, show the error message
        console.error('Error fetching question:', err);
        setError(err.response?.data?.message || 'Failed to load question');
      }
    });
  }, [lobbyId, questions, currentQuestionIndex, userAnswers, isExamMode, testCompleted]);

  // Improve handleNextQuestion to handle the case where the last question is answered
  const handleNextQuestion = () => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    } else if (!testCompleted) {
      // Last question reached, but don't auto-finish
      console.log("Last question reached. Please click 'Finish Test' button to see results.");
      // Could display a message to the user here
    }
  };

  const handlePrevQuestion = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(currentQuestionIndex - 1);
    }
  };

  // Make the finishTest function more robust
  const finishTest = async () => {
    try {
      console.log(`Sending finish request for lobby ${lobbyId}`);
      setSyncing(true);
      
      try {
        const response = await api.post(`/lobbies/lobbies/${lobbyId}/finish`, {});
        console.log(`Finish response:`, response.data);
        
        if (response.data.status === "ok") {
          setTestCompleted(true);
          
          // Clear timer if it's running
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
          }
          
          // Fetch test results
          fetchTestResults();
        }
      } catch (err) {
        console.error('Error finishing test:', err, err.response?.data);
        
        // Special handling for "Test not active" or "already completed" errors
        // These are actually not errors for us - the test is already finished
        if (err.response?.status === 400 && 
            (err.response?.data?.message?.includes("не активен") || 
             err.response?.data?.message?.includes("не запущен") ||
             err.response?.data?.message?.includes("уже завершен"))) {
          console.log("Test already finished, fetching results anyway");
          setTestCompleted(true);
          
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
          }
          
          // Still try to fetch results
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
      console.log(`Fetching test results for lobby ${lobbyId}`);
      const response = await api.get(`/lobbies/lobbies/${lobbyId}/results`);
      
      console.log(`Results response:`, response.data);
      
      if (response.data.status === "ok") {
        setTestResults(response.data.data);
        // Clear any saved timer
        localStorage.removeItem(`exam_timer_${lobbyId}`);
        // Clear saved answers
        localStorage.removeItem(`userAnswers_${lobbyId}`);
        // Clear saved question index
        localStorage.removeItem(`currentQuestionIndex_${lobbyId}`);
      } else {
        console.error('Error in test results response:', response.data);
        setError(response.data.message || 'Failed to load test results');
      }
    } catch (err) {
      console.error('Error fetching test results:', err);
      console.error('Error response data:', err.response?.data);
      // If we get a 404 or the lobby is no longer active, we'll show a basic results page
      if (err.response?.status === 404 || 
          (err.response?.data?.message && err.response?.data?.message.includes("Тест не активен"))) {
        console.log("Test is completed but detailed results unavailable. Showing basic completion page.");
        
        // Create a minimal results object
        setTestResults({
          user_result: {
            correct_count: Object.values(userAnswers).filter((_, i) => 
              correctAnswer && i === correctAnswer).length,
            total_questions: questions.length,
            percentage: Math.round((Object.values(userAnswers).filter((_, i) => 
              correctAnswer && i === correctAnswer).length / questions.length) * 100),
            passed: false // We don't know, so assume not passed
          }
        });
        
        // Clear any saved timer
        localStorage.removeItem(`exam_timer_${lobbyId}`);
        // Clear saved answers
        localStorage.removeItem(`userAnswers_${lobbyId}`);
        // Clear saved question index
        localStorage.removeItem(`currentQuestionIndex_${lobbyId}`);
      } else {
        setError(err.response?.data?.message || 'Failed to load test results');
      }
    }
  };

  // Format time from seconds to MM:SS
  const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds < 10 ? '0' : ''}${remainingSeconds}`;
  };

  // Return to dashboard
  const handleReturnToDashboard = () => {
    navigate('/dashboard');
  };

  // NO IMAGE placeholder when there's no media  
  const NoMediaPlaceholder = () => (    
    <div style={{       
      width: '100%',       
      height: '240px',       
      background: '#f1f1f1',       
      display: 'flex',       
      alignItems: 'center',       
      justifyContent: 'center',      
      borderRadius: '8px',      
      marginBottom: '20px'    
    }}>      
      <span style={{ color: '#555', fontSize: '16px', fontWeight: 'bold' }}>NO IMAGE</span>    
    </div>  
  );

  // Simplified function just for compatibility with existing code
  const fetchQuestionMedia = async (questionId) => {
    // This function is now deprecated - all media handling is done in fetchCurrentQuestion
    console.log("Media is handled directly by the video/img elements");
    return true;
  };

  // Loading state
  if (loading) {
    return (
      <div className={`app-container ${theme === 'dark' ? 'dark-theme' : ''}`}>
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
          <div className="test-loading">
            <div className="loading-spinner"></div>
            <p>{getTranslation('loading')}</p>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`app-container ${theme === 'dark' ? 'dark-theme' : ''}`}>
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
          <div className="test-error">
            <FaTimes size={48} color="red" />
            <h2>{getTranslation('error')}</h2>
            <p>{error}</p>
            <button className="primary-button" onClick={handleReturnToDashboard}>
              {getTranslation('returnToDashboard')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Test completed and results available
  if (testCompleted && testResults) {
    return (
      <div className={`app-container ${theme === 'dark' ? 'dark-theme' : ''}`}>
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
            <h1>{getTranslation('testResults')}</h1>
            
            <div className="results-summary">
              <div className="result-score">
                <h2>{testResults.user_result.percentage}%</h2>
                <p>{getTranslation('correctAnswers')}: {testResults.user_result.correct_count}/{testResults.user_result.total_questions}</p>
              </div>
              
              <div className="result-passed">
                {testResults.user_result.passing_score ? (
                  <div className="passed">
                    <FaCheck size={32} />
                    <span>{getTranslation('passed')}</span>
                  </div>
                ) : (
                  <div className="failed">
                    <FaTimes size={32} />
                    <span>{getTranslation('failed')}</span>
                  </div>
                )}
              </div>
            </div>
            
            {testResults.sections && testResults.sections.length > 0 && (
              <div className="sections-results">
                <h3>{getTranslation('resultsBySection')}</h3>
                <div className="sections-grid">
                  {testResults.sections.map((section, index) => (
                    <div key={index} className="section-result">
                      <h4>{section.section}</h4>
                      <div className="section-score">
                        <div className="progress-bar">
                          <div className="progress" style={{ width: `${section.percentage}%` }}></div>
                        </div>
                        <span>{section.percentage}%</span>
                      </div>
                      <p>{section.correct}/{section.total}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {testResults.user_result.best_section && (
              <div className="best-worst-sections">
                <div className="best-section">
                  <h4>{getTranslation('bestSection')}</h4>
                  <p>{testResults.user_result.best_section.section}</p>
                  <div className="section-score">
                    <div className="progress-bar">
                      <div className="progress" style={{ width: `${testResults.user_result.best_section.percentage}%` }}></div>
                    </div>
                    <span>{testResults.user_result.best_section.percentage}%</span>
                  </div>
                </div>
                
                {testResults.user_result.worst_section && (
                  <div className="worst-section">
                    <h4>{getTranslation('worstSection')}</h4>
                    <p>{testResults.user_result.worst_section.section}</p>
                    <div className="section-score">
                      <div className="progress-bar">
                        <div className="progress" style={{ width: `${testResults.user_result.worst_section.percentage}%` }}></div>
                      </div>
                      <span>{testResults.user_result.worst_section.percentage}%</span>
                    </div>
                  </div>
                )}
              </div>
            )}
            
            <button className="primary-button" onClick={handleReturnToDashboard}>
              {getTranslation('returnToDashboard')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Active test
  return (
    <div className={`app-container ${theme === 'dark' ? 'dark-theme' : ''}`}>
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
        <div className="test-page">
          <div className="test-header">
            <div className="test-progress">
              <div className="progress-text">
                {getTranslation('question')} {currentQuestionIndex + 1}/{questions.length}
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
                <div className="test-timer">
                  <div className={`timer ${timeLeft < 60 ? 'timer-warning' : ''}`}>
                    {formatTime(timeLeft)}
                  </div>
                </div>
              )}
              
              <button 
                className="finish-button" 
                onClick={() => {
                  if (confirm(getTranslation('confirmFinishTest'))) {
                    finishTest();
                  }
                }}
              >
                {getTranslation('finishEarly')}
              </button>
              
              <button 
                className="history-button" 
                onClick={toggleHistorySidebar}
                title={getTranslation('questionHistory')}
              >
                <FaHistory />
              </button>
            </div>
          </div>
          
          <div className="test-content">
            {/* Question History Sidebar */}
            <div className={`question-history-sidebar ${isHistorySidebarOpen ? 'open' : ''}`}>
              <h3>{getTranslation('questionHistory')}</h3>
              <div className="question-list">
                {questions.map((questionId, index) => {
                  let statusClass = '';
                  if (userAnswers[questionId] !== undefined) {
                    const isCorrect = !isExamMode && correctAnswer !== null && userAnswers[questionId] === correctAnswer;
                    statusClass = isCorrect ? 'correct' : (isExamMode ? '' : 'incorrect');
                  }
                  
                  // Only make current question or answered questions clickable
                  const isClickable = userAnswers[questionId] !== undefined || index === currentQuestionIndex;
                  
                  return (
                    <div 
                      key={questionId} 
                      className={`question-item ${index === currentQuestionIndex ? 'active' : ''} ${statusClass} ${isClickable ? 'clickable' : 'disabled'}`}
                      onClick={() => isClickable && setCurrentQuestionIndex(index)}
                    >
                      <span className="question-number">{index + 1}</span>
                      {userAnswers[questionId] !== undefined && !isExamMode && (
                        <span className="answer-indicator">
                          {statusClass === 'correct' ? <FaCheck className="correct-icon" /> : <FaTimes className="incorrect-icon" />}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
            
            {/* Main Question Content */}
            <div className="question-main-content">
              {syncing && (
                <div className="syncing-message">
                  <div className="loading-spinner"></div>
                  <p>{getTranslation('syncingWithServer')}</p>
                </div>
              )}
              
              {currentQuestion && (
                <div className="question-container">
                  <div className="question-text">
                    <h2>
                      {currentQuestion && localizeText(currentQuestion.question_text)}
                    </h2>
                    {/* Debug display of media type */}
                    <div style={{fontSize: '10px', color: 'gray', marginTop: '5px'}}>
                      Debug: Media type: {currentQuestion ? currentQuestion.media_type : 'none'}, 
                      Has media: {currentQuestion && currentQuestion.has_media ? 'Yes' : 'No'},
                      Media URL: {currentQuestion && currentQuestion.media_url ? 'Set' : 'Missing'}
                    </div>
                  </div>
                  
                  {mediaLoading ? (
                    <div className="media-loading">
                      <div className="progress-container">
                        <div className="progress-bar">
                          <div className="progress" style={{ width: `${mediaProgress}%` }}></div>
                        </div>
                        <div className="progress-text">{mediaProgress}%</div>
                      </div>
                      <p>{getTranslation('loadingMedia')}</p>
                    </div>
                  ) : (
                    <>
                      <div className="question-media">
                        {/* Если есть видео-объяснение и пользователь уже ответил, показываем его вместо основного видео */}
                        {answerSubmitted && !isExamMode && afterAnswerMedia && currentQuestion && 
                         currentQuestion.has_after_answer_media ? (
                          currentQuestion.after_answer_media_type === 'video' ? (
                            <div style={{ width: '100%', position: 'relative', paddingBottom: '56.25%', height: 0, overflow: 'hidden' }}>
                              <video 
                                controls
                                autoPlay
                                playsInline
                                className="question-video"
                                poster="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgdmlld0JveD0iMCAwIDIwMCAyMDAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjIwMCIgaGVpZ2h0PSIyMDAiIGZpbGw9IiMzMzMzMzMiLz48dGV4dCB4PSI0MCIgeT0iMTAwIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTUiIGZpbGw9IiNmZmYiPkxvYWRpbmcgdmlkZW8uLi48L3RleHQ+PC9zdmc+"
                                onError={(e) => {
                                  console.error("Video explanation loading error:", e);
                                  e.target.onerror = null;
                                  // Show placeholder for failed video
                                  e.target.parentNode.innerHTML = `
                                    <div class="video-error" style="width: 100%; height: 240px; background: #f1f1f1; display: flex; align-items: center; justify-content: center">
                                      <span style="color: #555">Video explanation unavailable</span>
                                    </div>
                                  `;
                                }}
                                src={afterAnswerMedia}
                                style={{ 
                                  position: 'absolute',
                                  top: 0,
                                  left: 0,
                                  width: '100%',
                                  height: '100%'
                                }}
                                preload="metadata"
                              >
                                <p style={{ color: 'white', textAlign: 'center', marginTop: '20px' }}>
                                  Загрузка видео объяснения...
                                </p>
                              </video>
                            </div>
                          ) : (
                            <img 
                              src={afterAnswerMedia}
                              alt="Explanation image"
                              className="question-image"
                              onError={(e) => {
                                console.error("Image explanation loading error:", e);
                                e.target.onerror = null;
                                // Use inline SVG or data URI instead of external file
                                e.target.src = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgdmlld0JveD0iMCAwIDIwMCAyMDAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjIwMCIgaGVpZ2h0PSIyMDAiIGZpbGw9IiNmMWYxZjEiLz48dGV4dCB4PSIzNSIgeT0iMTAwIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTUiIGZpbGw9IiM1NTUiPkltYWdlIG5vdCBhdmFpbGFibGU8L3RleHQ+PC9zdmc+";
                              }}
                              onLoad={() => console.log("Explanation image loaded successfully")}
                            />
                          )
                        ) : (
                          // Показываем основное видео/изображение, если нет видео объяснения или пользователь еще не ответил
                          currentQuestion && currentQuestion.has_media && currentQuestion.media_url ? (
                            currentQuestion.media_type === 'video' ? (
                              videoError ? (
                                <div className="video-error">
                                  <p>{getTranslation('videoError')}</p>
                                  <div style={{ width: '100%', height: '240px', background: '#f1f1f1', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                    <span style={{ color: '#555' }}>Video unavailable</span>
                                  </div>
                                </div>
                              ) : (
                                <div style={{ width: '100%', position: 'relative', paddingBottom: '56.25%', height: 0, overflow: 'hidden' }}>
                                  <video 
                                    key={`video_${currentQuestion.id}_${videoBlobUrl || 'placeholder'}`}
                                    controls
                                    autoPlay
                                    muted={false}
                                    playsInline
                                    className="question-video"
                                    poster="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgdmlld0JveD0iMCAwIDIwMCAyMDAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjIwMCIgaGVpZ2h0PSIyMDAiIGZpbGw9IiMzMzMzMzMiLz48dGV4dCB4PSI0MCIgeT0iMTAwIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTUiIGZpbGw9IiNmZmYiPkxvYWRpbmcgdmlkZW8uLi48L3RleHQ+PC9zdmc+"
                                    onError={(e) => {
                                      console.error("Video loading error:", e);
                                      console.log("Video source that failed:", videoBlobUrl || currentQuestion.media_url);
                                      // Try to create a more detailed error message
                                      try {
                                        console.log("Video element:", e.target);
                                        console.log("Video error code:", e.target.error?.code);
                                        console.log("Video error message:", e.target.error?.message);
                                      } catch (err) {
                                        console.error("Error in video error logging:", err);
                                      }
                                      setVideoError(true);
                                      e.target.onerror = null;
                                    }}
                                    preload="metadata"
                                    style={{ 
                                      position: 'absolute',
                                      top: 0,
                                      left: 0,
                                      width: '100%',
                                      height: '100%'
                                    }}
                                    onLoadStart={() => console.log("Video load started")}
                                    onLoadedData={() => console.log("Video data loaded successfully")}
                                    onAbort={() => console.error("Video loading aborted")}
                                    onStalled={() => console.error("Video loading stalled")}
                                    src={videoBlobUrl || ""}
                                  >
                                    {!videoBlobUrl && (
                                      <p style={{ color: 'white', textAlign: 'center', marginTop: '20px' }}>
                                        Загрузка видео...
                                      </p>
                                    )}
                                  </video>
                                </div>
                              )
                            ) : (
                              <img 
                                key={`image_${currentQuestion.id}_${new Date().getTime()}`}
                                src={currentQuestion.media_url}
                                alt="Question image"
                                className="question-image"
                                onError={(e) => {
                                  console.error("Image loading error:", e);
                                  e.target.onerror = null;
                                  // Use inline SVG or data URI instead of external file
                                  e.target.src = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgdmlld0JveD0iMCAwIDIwMCAyMDAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjIwMCIgaGVpZ2h0PSIyMDAiIGZpbGw9IiNmMWYxZjEiLz48dGV4dCB4PSIzNSIgeT0iMTAwIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTUiIGZpbGw9IiM1NTUiPkltYWdlIG5vdCBhdmFpbGFibGU8L3RleHQ+PC9zdmc+";
                                }}
                                onLoad={() => console.log("Image loaded successfully")}
                                crossOrigin="anonymous"
                              />
                            )
                          ) : (
                            // Show "NO IMAGE" when no media is available
                            <NoMediaPlaceholder />
                          )
                        )}
                      </div>
                      
                      <div className="answer-options">
                        {currentQuestion && currentQuestion.answers && currentQuestion.answers.map((answer, index) => {
                          // Get answer text in current language
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
                            >
                              <div className="answer-label">{String.fromCharCode(65 + index)}</div>
                              <div className="answer-text">{answerText}</div>
                            </div>
                          );
                        })}
                      </div>
                      
                      {answerSubmitted && !isExamMode && (
                        <div className="answer-explanation">
                          {explanation && (
                            <div className="explanation-text">
                              <h3>{getTranslation('explanation')}</h3>
                              <p>{localizeText(explanation)}</p>
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
          
          <div className="test-navigation">
            <button 
              className="nav-button prev"
              onClick={handlePrevQuestion}
              disabled={currentQuestionIndex === 0 || !answerSubmitted}
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
    </div>
  );
};

export default TestPage; 