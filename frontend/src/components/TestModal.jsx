import React, { useState, useEffect } from 'react';
import { FaTimes, FaCheck, FaCrown, FaCheckCircle, FaExclamationCircle, FaClock } from 'react-icons/fa';
import { useNavigate } from 'react-router-dom';
import api from '../utils/axios';
import '../pages/dashboard/styles.css';

const TestModal = ({ isOpen, onClose, category, subscription, translations: t, isDarkTheme }) => {
  const [examMode, setExamMode] = useState(false);
  const [selectedSections, setSelectedSections] = useState([]);
  const [sectionsData, setSectionsData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [checkingActiveLobby, setCheckingActiveLobby] = useState(true);
  const [activeLobby, setActiveLobby] = useState(null);
  
  const navigate = useNavigate();
  
  // Section selection available only for VIP, Royal, or School subscriptions
  const canSelectSections = subscription && 
    ['vip', 'royal', 'school'].includes(subscription.subscription_type?.toLowerCase());
  
  // Check for active lobby on component mount
  useEffect(() => {
    const checkActiveLobby = async () => {
      try {
        setCheckingActiveLobby(true);
        console.log("Checking for active lobby");
        const response = await api.get('/lobbies/active-lobby');
        
        console.log("Active lobby check response:", response.data);
        if (response.data.status === "ok") {
          const lobbyData = response.data.data;
          if (lobbyData.has_active_lobby) {
            console.log("Active lobby found:", lobbyData);
            setActiveLobby(lobbyData);
          } else {
            console.log("No active lobby");
            setActiveLobby(null);
          }
        } else {
          console.error("Error in active lobby check response:", response.data);
          setError(response.data.message || t['failedToCheckActiveLobby'] || 'Failed to check for active tests');
        }
      } catch (error) {
        console.error('Error checking for active lobby:', error);
        console.error('Error response:', error.response?.data);
        setError(error.response?.data?.message || t['failedToCheckActiveLobby'] || 'Failed to check for active tests');
      } finally {
        setCheckingActiveLobby(false);
      }
    };

    checkActiveLobby();
  }, [t]);

  // Format time from seconds to HH:MM:SS
  const formatTime = (totalSeconds) => {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  // Prevent background scrolling when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.classList.add('modal-open');
    }
    
    return () => {
      document.body.classList.remove('modal-open');
    };
  }, [isOpen]);
    
  // PDD sections
  const PDD_SECTIONS = [
    {"uid":"polozheniya","title":"Общие положения","order":10},
    {"uid":"voditeli","title":"Общие обязанности водителей","order":20},
    {"uid":"peshehody","title":"Обязанности пешеходов","order":30},
    {"uid":"cyclists","title":"Обязанности велосипедистов","order":40},
    {"uid":"signs","title":"Дорожные знаки","order":50},
    {"uid":"razmetka","title":"Дорожная разметка","order":60},
    {"uid":"svetofor","title":"Сигналы светофора","order":70},
    {"uid":"regulirovka","title":"Регулирование дорожного движения","order":80},
    {"uid":"skorost","title":"Скорость движения","order":90},
    {"uid":"obgon","title":"Обгон, опережение, встречный разъезд","order":100},
    {"uid":"ostanovka","title":"Остановка и стоянка","order":110},
    {"uid":"crossing","title":"Проезд перекрестков","order":120},
    {"uid":"perehod","title":"Пешеходные переходы","order":130},
    {"uid":"bezopasnost","title":"Безопасность движения","order":140},
    {"uid":"first-aid","title":"Первая помощь","order":150}
  ];
    
  // Handle overlay click (close modal only if clicking outside content)
  const handleOverlayClick = (e) => {
    if (e.target.classList.contains('test-modal-overlay')) {
      onClose();
    }
  };

  // Toggle section selection
  const toggleSection = (uid) => {
    if (!canSelectSections) return;
    
    setSelectedSections(prev => {
      if (prev.includes(uid)) {
        return prev.filter(id => id !== uid);
      } else {
        return [...prev, uid];
      }
    });
  };
  
  // Select all sections
  const selectAllSections = () => {
    if (!canSelectSections) return;
    const allUids = PDD_SECTIONS.map(section => section.uid);
    setSelectedSections(allUids);
  };
  
  // Deselect all sections
  const deselectAllSections = () => {
    if (!canSelectSections) return;
    setSelectedSections([]);
  };

  // Redirect to active test
  const continueActiveTest = () => {
    if (activeLobby && activeLobby.lobby_id) {
      console.log(`Redirecting to active test: /test/${activeLobby.lobby_id}`);
      navigate(`/test/${activeLobby.lobby_id}`);
      
      onClose();
    } else {
      console.error("Cannot redirect: No active lobby ID found");
      setError(t['noActiveLobby'] || "No active test found");
    }
  };
  
  // Handle start test button click
  const handleStartTest = async () => {
    // If there's an active test, redirect to it instead of creating a new one
    if (activeLobby) {
      console.log("Active lobby found, redirecting to it instead of creating a new one");
      continueActiveTest();
      return;
    }
    
    setError(null);
    setLoading(true);

    try {
      // Prepare categories based on selected category
      let categories = null;
      if (category) {
        if (category.title === 'A1, A, B1') {
          categories = ['A1', 'A', 'B1'];
        } else if (category.title === 'B, BE') {
          categories = ['B', 'BE'];
        } else if (category.title === 'C, C1') {
          categories = ['C', 'C1'];
        } else if (category.title === 'BC1') {
          categories = ['BC1'];
        } else if (category.title === 'D1, D, Tb') {
          categories = ['D1', 'D', 'Tb'];
        } else if (category.title === 'C1, CE, D1, DE') {
          categories = ['C1', 'CE', 'D1', 'DE'];
        } else if (category.title === 'Tm') {
          categories = ['Tm'];
        }
      }

      console.log("Creating new lobby with:", { 
        mode: 'solo', 
        categories, 
        pdd_sections: selectedSections.length > 0 ? selectedSections : null,
        exam_mode: examMode
      });

      // Create lobby
      const response = await api.post('/lobbies/lobbies', {
        mode: 'solo',
        categories: categories,
        pdd_section_uids: selectedSections.length > 0 ? selectedSections : null,
        exam_mode: examMode
      });

      console.log("Lobby creation response:", response.data);

      if (response.data.status === "ok") {
        // Navigate to test page with the created lobby id
        const lobbyId = response.data.data.lobby_id;
        console.log(`Successfully created lobby. Navigating to /test/${lobbyId}`);
        
        onClose();
        
        navigate(`/test/${lobbyId}`);
      } else {
        console.error("Error in response:", response.data);
        setError(response.data.message || t['failedToCreateTest'] || 'Failed to create test');
      }
    } catch (error) {
      console.error('Error creating test:', error);
      console.error('Error response:', error.response?.data);
      
      // Handle special case for active lobby
      if (error.response && error.response.status === 400 && error.response.data.details && error.response.data.details.active_lobby_id) {
        const { active_lobby_id, remaining_seconds } = error.response.data.details;
        
        console.log(`Found active lobby ${active_lobby_id} with ${remaining_seconds} seconds remaining`);
        
        // Store active lobby info
        setActiveLobby({
          has_active_lobby: true,
          lobby_id: active_lobby_id,
          remaining_seconds: remaining_seconds || 0
        });
        
        setError(error.response.data.message || t['activeTestExists'] || 'You have an active test. Please continue it or wait for it to expire.');
      } else {
        setError(error.response?.data?.message || t['failedToCreateTest'] || 'Failed to create test');
      }
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="test-modal-overlay" onClick={handleOverlayClick}>
      <div className={`test-modal ${isDarkTheme ? 'dark-theme' : ''}`}>
        <div className="test-modal-header">
          <h2>{t['test.startTest'] || 'Start Test'}</h2>
          <button className="close-button" onClick={onClose}>
            <FaTimes />
          </button>
        </div>

        <div className="test-modal-body">
          {/* Show active test notification if exists */}
          {activeLobby && activeLobby.has_active_lobby && (
            <div className="test-modal-error">
              <FaExclamationCircle className="error-icon" />
              <div>
                <p>{t['test.hasActiveTest'] || 'You already have an active test'}</p>
                {activeLobby.remaining_seconds > 0 && (
                  <div className="time-remaining">
                    <FaClock /> {t['test.timeRemaining'] || 'Time remaining'}: {formatTime(activeLobby.remaining_seconds)}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Show error message if any */}
          {error && !activeLobby && (
            <div className="test-modal-error">
              <FaExclamationCircle className="error-icon" />
              <div>{error}</div>
            </div>
          )}

          <div className="selected-category">
            <h3>{t['test.selectedCategory'] || 'Selected Category'}</h3>
            <div className="category-info">
              <div className="category-icon">
                {category.icon}
              </div>
              <div className="category-details">
                <h4>{category.title}</h4>
                <p>{category.description}</p>
                <div className="category-meta">
                  <div className={`level-badge ${
                    category.level === t['level.beginner'] || category.level === 'Beginner' ? 'level-beginner' :
                    category.level === t['level.intermediate'] || category.level === 'Intermediate' ? 'level-intermediate' :
                    'level-advanced'
                  }`}>
                    {category.level}
                  </div>
                  <div className="questions-count">
                    40 {t['questions'] || 'questions'}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="test-options">
            <div className="exam-mode-toggle">
              <label className="checkbox-container">
                <input 
                  type="checkbox" 
                  checked={examMode} 
                  onChange={() => setExamMode(!examMode)}
                />
                <span className="checkmark"></span>
                {t['test.examMode'] || 'Exam Mode'} 
                <span className="tooltip-container">
                  <span className="tooltip-text">
                    {t['test.examModeTooltip'] || 'In exam mode, you will have 40 minutes to complete the test and will only see correct answers at the end.'}
                  </span>
                </span>
              </label>
            </div>

            {(subscription && ['vip', 'royal', 'school'].includes(subscription.subscription_type?.toLowerCase())) && (
              <div className="sections-selection">
                <div className="sections-header">
                  <h3>{t['test.pddSections'] || 'PDD Sections'}</h3>
                  {canSelectSections && (
                    <div className="selection-actions">
                      <button onClick={selectAllSections}>
                        {t['selectAll'] || 'Select All'}
                      </button>
                      <button onClick={deselectAllSections}>
                        {t['deselectAll'] || 'Deselect All'}
                      </button>
                    </div>
                  )}
                </div>

                {!canSelectSections && (
                  <div className="premium-notice">
                    <FaCrown className="crown-icon" />
                    <span>
                      {t['test.sectionsPermission'] || 'Section selection available for VIP, Royal, and School subscriptions'}
                    </span>
                  </div>
                )}

                <div className="sections-list">
                  {PDD_SECTIONS.map(section => (
                    <div 
                      key={section.uid}
                      className={`section-item ${!canSelectSections ? 'disabled' : ''}`}
                      onClick={() => toggleSection(section.uid)}
                    >
                      <div className={`section-checkbox ${selectedSections.includes(section.uid) ? 'checked' : ''}`}>
                        {selectedSections.includes(section.uid) && <FaCheck />}
                      </div>
                      <span>{section.title}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="test-modal-footer">
          <button className="cancel-button" onClick={onClose} disabled={loading}>
            {t['cancel'] || 'Cancel'}
          </button>
          
          {activeLobby && activeLobby.has_active_lobby ? (
            <button 
              className="start-button" 
              onClick={continueActiveTest}
            >
              {t['test.continueTest'] || 'Continue Test'}
            </button>
          ) : (
            <button 
              className={`start-button ${loading ? 'loading' : ''}`} 
              onClick={handleStartTest}
              disabled={loading || checkingActiveLobby}
            >
              {loading ? <div className="button-spinner"></div> : t['test.startTest'] || 'Start Test'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default TestModal; 