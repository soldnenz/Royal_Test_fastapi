import React, { useState, useEffect } from 'react';
import { FaTimes, FaCheck, FaCrown, FaCheckCircle, FaExclamationCircle, FaClock } from 'react-icons/fa';
import { useNavigate } from 'react-router-dom';
import api from '../utils/axios';
import '../pages/dashboard/styles.css';

const TestModal = ({ isOpen, onClose, category, subscription, translations: t, isDark }) => {
  console.log('TestModal rendered with props:', { isOpen, category: category?.title, subscription: subscription?.subscription_type });
  
  const [examMode, setExamMode] = useState(false);
  const [sectionsData, setSectionsData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [checkingActiveLobby, setCheckingActiveLobby] = useState(true);
  const [activeLobby, setActiveLobby] = useState(null);
  
  const navigate = useNavigate();
  
  // Section selection available only for VIP, Royal, or School subscriptions
  const canSelectSections = subscription && 
    ['vip', 'royal', 'school'].includes(subscription.subscription_type?.toLowerCase());
  
  // PDD sections
  const PDD_SECTIONS = [
    {"uid":"polozheniya","title":t['testModal.sections.polozheniya'] || "Общие положения"},
    {"uid":"voditeli","title":t['testModal.sections.voditeli'] || "Общие обязанности водителей"},
    {"uid":"peshehody","title":t['testModal.sections.peshehody'] || "Обязанности пешеходов"},
    {"uid":"passazhiry","title":t['testModal.sections.passazhiry'] || "Обязанности пассажиров"},
    {"uid":"svetofor","title":t['testModal.sections.svetofor'] || "Сигналы светофора и регулировщика"},
    {"uid":"specsignaly","title":t['testModal.sections.specsignaly'] || "Применение специальных сигналов"},
    {"uid":"avarijka","title":t['testModal.sections.avarijka'] || "Применение аварийной сигнализации и знака аварийной остановки"},
    {"uid":"manevrirovanie","title":t['testModal.sections.manevrirovanie'] || "Маневрирование"},
    {"uid":"raspolozhenie","title":t['testModal.sections.raspolozhenie'] || "Расположение транспортных средств на проезжей части дороги"},
    {"uid":"speed","title":t['testModal.sections.speed'] || "Скорость движения"},
    {"uid":"obgon","title":t['testModal.sections.obgon'] || "Обгон, встречный разъезд"},
    {"uid":"ostanovka","title":t['testModal.sections.ostanovka'] || "Остановка и стоянка"},
    {"uid":"perekrestki","title":t['testModal.sections.perekrestki'] || "Проезд перекрёстков"},
    {"uid":"perehody","title":t['testModal.sections.perehody'] || "Пешеходные переходы и остановки маршрутных транспортных средств"},
    {"uid":"zhd","title":t['testModal.sections.zhd'] || "Движение через железнодорожные пути"},
    {"uid":"magistral","title":t['testModal.sections.magistral'] || "Движение по автомагистралям"},
    {"uid":"zhilaya-zona","title":t['testModal.sections.zhilaya-zona'] || "Движение в жилых зонах"},
    {"uid":"prioritet","title":t['testModal.sections.prioritet'] || "Приоритет маршрутных транспортных средств"},
    {"uid":"svetovye-pribory","title":t['testModal.sections.svetovye-pribory'] || "Пользование внешними световыми приборами и звуковыми сигналами"},
    {"uid":"buksirovka","title":t['testModal.sections.buksirovka'] || "Буксировка механических транспортных средств"},
    {"uid":"uchebnaya-ezda","title":t['testModal.sections.uchebnaya-ezda'] || "Учебная езда"},
    {"uid":"perevozka-passazhirov","title":t['testModal.sections.perevozka-passazhirov'] || "Перевозка пассажиров"},
    {"uid":"perevozka-gruzov","title":t['testModal.sections.perevozka-gruzov'] || "Перевозка грузов"},
    {"uid":"velosipedy-i-zhivotnye","title":t['testModal.sections.velosipedy-i-zhivotnye'] || "Дополнительные требования к движению велосипедов, мопедов, гужевых повозок, а так же животных"},
    {"uid":"invalidy","title":t['testModal.sections.invalidy'] || "Обеспечение движения людей с нарушениями опорно-двигательного аппарата"},
    {"uid":"znaki","title":t['testModal.sections.znaki'] || "Дорожные знаки"},
    {"uid":"razmetka","title":t['testModal.sections.razmetka'] || "Дорожная разметка и её характеристики"},
    {"uid":"dopusk","title":t['testModal.sections.dopusk'] || "Основные положения по допуску транспортных средств к эксплуатации"},
    {"uid":"obdzh","title":t['testModal.sections.obdzh'] || "ОБДЖ (Обеспечение безопасности дорожного движения)"},
    {"uid":"administrativka","title":t['testModal.sections.administrativka'] || "Административка"},
    {"uid":"medicina","title":t['testModal.sections.medicina'] || "Медицина"},
    {"uid":"dtp","title":t['testModal.sections.dtp'] || "ДТП"},
    {"uid":"osnovy-upravleniya","title":t['testModal.sections.osnovy-upravleniya'] || "Основы управления транспортным средством и безопасность движения"}
  ];

  const [selectedSections, setSelectedSections] = useState(PDD_SECTIONS.map(section => section.uid));
  
  // Check for active lobby on component mount
  useEffect(() => {
    const checkActiveLobby = async () => {
      try {
        setCheckingActiveLobby(true);
        console.log("Checking for active lobby");
        const response = await api.get('/global-lobby/active-lobby');
        
        console.log("Active lobby check response:", response.data);
        console.log("Response data object:", JSON.stringify(response.data.data, null, 2));
        
        if (response.data.status === "ok") {
          const lobbyData = response.data.data;
          console.log("Lobby data has_active_lobby:", lobbyData.has_active_lobby);
          console.log("Full lobby data:", lobbyData);
          
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
      document.body.style.overflow = 'hidden';
    }
    
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);
    
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
  const continueActiveTest = async () => {
    if (activeLobby && activeLobby.lobby_id) {
      try {
        // Get lobby info to determine if it's multiplayer
        const response = await api.get(`/global-lobby/lobbies/${activeLobby.lobby_id}`);
        
        if (response.data.status === "ok") {
          const lobbyData = response.data.data;
          
          if (lobbyData.mode === 'multiplayer') {
            console.log(`Redirecting to multiplayer test: /multiplayer/test/${activeLobby.lobby_id}`);
            navigate(`/multiplayer/test/${activeLobby.lobby_id}`);
          } else {
            console.log(`Redirecting to solo test: /test/${activeLobby.lobby_id}`);
            navigate(`/test/${activeLobby.lobby_id}`);
          }
        } else {
          console.log(`Fallback: Redirecting to test: /test/${activeLobby.lobby_id}`);
          navigate(`/test/${activeLobby.lobby_id}`);
        }
      } catch (error) {
        console.error('Error fetching lobby info, using fallback:', error);
        console.log(`Fallback: Redirecting to test: /test/${activeLobby.lobby_id}`);
        navigate(`/test/${activeLobby.lobby_id}`);
      }
      
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
      const response = await api.post('/global-lobby/lobbies', {
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
      console.error('Full error object:', JSON.stringify(error, null, 2));
      console.error('Error response:', error.response?.data);
      console.error('Error response details:', JSON.stringify(error.response?.data, null, 2));
      
      // Handle special case for active lobby
      if (error.response && error.response.status === 400) {
        const errorDetail = error.response.data.detail;
        
        // Check if the detail is an object with active_lobby_id (new format)
        if (errorDetail && typeof errorDetail === 'object' && errorDetail.active_lobby_id) {
          const { active_lobby_id, remaining_seconds, message } = errorDetail;
          
          console.log(`Found active lobby ${active_lobby_id} with ${remaining_seconds} seconds remaining`);
          
          // Store active lobby info
          setActiveLobby({
            has_active_lobby: true,
            lobby_id: active_lobby_id,
            remaining_seconds: remaining_seconds || 0
          });
          
          setError(message || t['activeTestExists'] || 'You have an active test. Please continue it or wait for it to expire.');
        } 
        // Check if the detail is an object with details.active_lobby_id (old format)
        else if (error.response.data.details && error.response.data.details.active_lobby_id) {
          const { active_lobby_id, remaining_seconds } = error.response.data.details;
          
          console.log(`Found active lobby ${active_lobby_id} with ${remaining_seconds} seconds remaining`);
          
          // Store active lobby info
          setActiveLobby({
            has_active_lobby: true,
            lobby_id: active_lobby_id,
            remaining_seconds: remaining_seconds || 0
          });
          
          setError(error.response.data.message || t['activeTestExists'] || 'You have an active test. Please continue it or wait for it to expire.');
        }
        // Handle string detail (simple error message)
        else {
          setError(errorDetail || error.response?.data?.message || t['failedToCreateTest'] || 'Failed to create test');
        }
      } else {
        setError(error.response?.data?.message || t['failedToCreateTest'] || 'Failed to create test');
      }
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) {
    console.log('TestModal not rendering because isOpen is false');
    return null;
  }

  console.log('TestModal rendering modal content');

  return (
    <div className="test-modal-overlay" onClick={handleOverlayClick}>
      <div className={`test-modal ${isDark ? 'dark-theme' : ''}`}>
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
                    {category.questions || 40} {t['questions'] || 'questions'}
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
                    {t['test.examModeTooltip'] || `В экзаменационном режиме у вас будет ${category.questions || 40} минут на прохождение теста и вы увидите правильные ответы только в конце.`}
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
              className="start-button continue-button" 
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