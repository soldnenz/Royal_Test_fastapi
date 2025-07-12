import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLanguage } from '../../contexts/LanguageContext';
import { useTheme } from '../../contexts/ThemeContext';
import { translations } from '../../translations/translations';
import api from '../../utils/axios';
import Header from '../../components/Header';
import Sidebar from '../../components/dashboard/DashboardSidebar';
import { 
  FaTimes, 
  FaCheck, 
  FaCrown, 
  FaGraduationCap,
  FaArrowLeft,
  FaArrowRight,
  FaUsers,
  FaQuestionCircle,
  FaCog,
  FaGamepad
} from 'react-icons/fa';
import { 
  MdDirectionsBike, 
  MdDirectionsCar, 
  MdLocalShipping, 
  MdTimer 
} from 'react-icons/md';
import { FaTruck, FaTruckMoving, FaBusAlt } from 'react-icons/fa';
import './CreateLobbyPage.css';

const CreateLobbyPage = () => {
  const { language } = useLanguage();
  const t = translations[language];
  const { isDark } = useTheme();
  const navigate = useNavigate();
  
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [subscription, setSubscription] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  
  // Form data
  const [formData, setFormData] = useState({
    categories: [],
    sections: [],
    questionsCount: 40,
    maxParticipants: 8,
    examMode: false
  });

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

  // Available categories
  const CATEGORIES = [
    {
      id: 'cat1',
      title: 'A1, A, B1',
      description: t['test.motorcycle_license'] || 'Motorcycle License',
      icon: <MdDirectionsBike size={24} />,
      allowedPlans: ['economy', 'vip', 'royal', 'school'],
      categories: ['A1', 'A', 'B1'],
      color: 'emerald'
    },
    {
      id: 'cat2',
      title: 'B, BE',
      description: t['test.car_license'] || 'Car License',
      icon: <MdDirectionsCar size={24} />,
      allowedPlans: ['economy', 'vip', 'royal', 'school'],
      categories: ['B', 'BE'],
      color: 'golden',
      popular: true
    },
    {
      id: 'cat3',
      title: 'C, C1',
      description: t['test.truck_license'] || 'Truck License',
      icon: <FaTruck size={24} />,
      allowedPlans: ['vip', 'royal', 'school'],
      categories: ['C', 'C1'],
      color: 'amber'
    },
    {
      id: 'cat4',
      title: 'BC1',
      description: t['test.commercial_license'] || 'Commercial License',
      icon: <FaTruckMoving size={24} />,
      allowedPlans: ['vip', 'royal', 'school'],
      categories: ['BC1'],
      color: 'orange'
    },
    {
      id: 'cat5',
      title: 'D1, D, Tb',
      description: t['test.bus_license'] || 'Bus License',
      icon: <FaBusAlt size={24} />,
      allowedPlans: ['vip', 'royal', 'school'],
      categories: ['D1', 'D', 'Tb'],
      color: 'amber'
    },
    {
      id: 'cat6',
      title: 'C1, CE, D1, DE',
      description: t['test.heavy_vehicle_license'] || 'Heavy Vehicle License',
      icon: <MdLocalShipping size={24} />,
      allowedPlans: ['vip', 'royal', 'school'],
      categories: ['C1', 'CE', 'D1', 'DE'],
      color: 'red'
    },
    {
      id: 'cat7',
      title: 'Tm',
      description: t['test.tram_license'] || 'Tram License',
      icon: <MdTimer size={24} />,
      allowedPlans: ['vip', 'royal', 'school'],
      categories: ['Tm'],
      color: 'orange'
    }
  ];

  // Fetch subscription data
  useEffect(() => {
    const fetchSubscription = async () => {
      try {
        const response = await api.get('/users/my/subscription');
        if (response.data.status === "ok") {
          const subData = response.data.data;
          if (subData.has_subscription) {
            setSubscription({
              subscription_type: subData.subscription_type,
              expires_at: subData.expires_at,
              days_left: subData.days_left,
              duration_days: subData.duration_days
            });
          }
        }
      } catch (error) {
        console.error('Error fetching subscription:', error);
        setError(t['failedToLoadSubscription'] || 'Failed to load subscription data');
      }
    };

    fetchSubscription();
  }, [t]);

  // Check if user can create lobby
  const canCreateLobby = subscription && 
    ['royal', 'school'].includes(subscription.subscription_type?.toLowerCase());

  // Check if category is available
  const isCategoryAvailable = (category) => {
    if (!subscription) return false;
    return category.allowedPlans.includes(subscription.subscription_type?.toLowerCase());
  };

  // Handle category selection
  const toggleCategory = (categoryId) => {
    const newCategories = formData.categories.includes(categoryId)
      ? formData.categories.filter(id => id !== categoryId)
      : [...formData.categories, categoryId];
    
    setFormData(prev => ({ ...prev, categories: newCategories }));
  };

  // Handle section selection
  const toggleSection = (sectionUid) => {
    const newSections = formData.sections.includes(sectionUid)
      ? formData.sections.filter(uid => uid !== sectionUid)
      : [...formData.sections, sectionUid];
    
    setFormData(prev => ({ ...prev, sections: newSections }));
  };

  // Select all sections
  const selectAllSections = () => {
    setFormData(prev => ({ ...prev, sections: PDD_SECTIONS.map(s => s.uid) }));
  };

  // Deselect all sections
  const deselectAllSections = () => {
    setFormData(prev => ({ ...prev, sections: [] }));
  };

  // Handle next step
  const handleNext = () => {
    if (step === 1 && formData.categories.length === 0) {
      setError(t['selectAtLeastOneCategory'] || 'Please select at least one category');
      return;
    }
    if (step === 2 && formData.sections.length === 0) {
      setError(t['selectAtLeastOneSection'] || 'Please select at least one section');
      return;
    }
    
    setError('');
    setStep(prev => prev + 1);
  };

  // Handle previous step
  const handlePrevious = () => {
    setError('');
    setStep(prev => prev - 1);
  };

  // Create lobby
  const handleCreateLobby = async () => {
    try {
      setLoading(true);
      setError('');

      // Convert category IDs to actual categories
      const selectedCategoryObjects = CATEGORIES.filter(cat => formData.categories.includes(cat.id));
      const allCategories = selectedCategoryObjects.flatMap(cat => cat.categories);

      const lobbyData = {
        mode: 'multiplayer',
        categories: allCategories,
        pdd_section_uids: formData.sections,
        questions_count: formData.questionsCount,
        exam_mode: formData.examMode,
        max_participants: formData.maxParticipants,
        status: 'waiting'
      };

      console.log('Creating lobby with data:', lobbyData);
      
      const response = await api.post('/multiplayer/lobbies', lobbyData);
      
      if (response.data.status === 'ok') {
        const lobbyId = response.data.data.lobby_id;
        const wsToken = response.data.data.ws_token;

        // Сохраняем WS токен
        if (wsToken) {
          localStorage.removeItem('ws_token');
          localStorage.setItem('ws_token', wsToken);
        }

        console.log('Lobby created successfully:', lobbyId);
        navigate(`/multiplayer/lobby/${lobbyId}`);
      } else {
        setError(response.data.message || t['failedToCreateLobby'] || 'Failed to create lobby');
      }
    } catch (error) {
      console.error('Error creating lobby:', error);
      setError(error.response?.data?.message || t['failedToCreateLobby'] || 'Failed to create lobby');
    } finally {
      setLoading(false);
    }
  };

  if (!canCreateLobby) {
    return (
      <div className={`create-lobby-page ${isDark ? 'dark-theme' : ''}`}>
        <div className="access-denied">
          <div className="access-denied-icon">
            <FaCrown />
          </div>
          <h2>{t['accessDenied'] || 'Access Denied'}</h2>
          <p>{t['needRoyalOrSchool'] || 'You need Royal or School subscription to create lobbies'}</p>
          <button className="back-btn" onClick={() => navigate(-1)}>
            <FaArrowLeft />
            {t['goBack'] || 'Go Back'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`create-lobby-page ${isDark ? 'dark-theme' : ''}`}>
      <Header />
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      
      <div className="main-content">
        <div className="create-lobby-container">
        {/* Header */}
        <div className="page-header">
          <div className="header-left">
            <button className="sidebar-toggle-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <button className="back-btn" onClick={() => navigate(-1)}>
              <FaArrowLeft />
            </button>
          </div>
          <div className="header-content">
            <h1>{t['createLobby'] || 'Create Lobby'}</h1>
            <div className="step-indicator">
              <span className="current-step">{step}</span>
              <span className="step-separator">/</span>
              <span className="total-steps">4</span>
            </div>
          </div>
          <div className="subscription-badge">
            {subscription?.subscription_type === 'royal' ? <FaCrown /> : <FaGraduationCap />}
            <span>{subscription?.subscription_type?.toUpperCase()}</span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${(step / 4) * 100}%` }}></div>
        </div>

        {/* Error message */}
        {error && (
          <div className="error-message">
            <FaTimes />
            <span>{error}</span>
          </div>
        )}

        {/* Step content */}
        <div className="step-content">
          {step === 1 && (
            <div className="step-section">
              <div className="step-header">
                <h2>{t['selectCategories'] || 'Select Categories'}</h2>
                <p>{t['selectCategoriesDescription'] || 'Choose which license categories to include in the test'}</p>
              </div>
              
              <div className="categories-grid">
                {CATEGORIES.map(category => (
                  <div
                    key={category.id}
                    className={`category-card ${
                      formData.categories.includes(category.id) ? 'selected' : ''
                    } ${!isCategoryAvailable(category) ? 'disabled' : ''}`}
                    onClick={() => isCategoryAvailable(category) && toggleCategory(category.id)}
                  >
                    {category.popular && (
                      <div className="popular-badge">
                        <span>{t['popular'] || 'Popular'}</span>
                      </div>
                    )}
                    
                    <div className={`category-icon color-${category.color}`}>
                      {category.icon}
                    </div>
                    
                    <div className="category-info">
                      <h3>{category.title}</h3>
                      <p>{category.description}</p>
                    </div>
                    
                    {formData.categories.includes(category.id) && (
                      <div className="selection-check">
                        <FaCheck />
                      </div>
                    )}
                    
                    {!isCategoryAvailable(category) && (
                      <div className="disabled-overlay">
                        <span>{t['notAvailable'] || 'Not Available'}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="step-section">
              <div className="step-header">
                <h2>{t['selectSections'] || 'Select PDD Sections'}</h2>
                <p>{t['selectSectionsDescription'] || 'Choose which PDD sections to include in questions'}</p>
                <div className="selection-actions">
                  <button onClick={selectAllSections} className="action-btn">
                    {t['selectAll'] || 'Select All'}
                  </button>
                  <button onClick={deselectAllSections} className="action-btn">
                    {t['deselectAll'] || 'Deselect All'}
                  </button>
                </div>
              </div>
              
              <div className="sections-list">
                {PDD_SECTIONS.map(section => (
                  <div
                    key={section.uid}
                    className={`section-item ${formData.sections.includes(section.uid) ? 'selected' : ''}`}
                    onClick={() => toggleSection(section.uid)}
                  >
                    <div className="section-checkbox">
                      {formData.sections.includes(section.uid) && <FaCheck />}
                    </div>
                    <span>{section.title}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="step-section">
              <div className="step-header">
                <h2>{t['testSettings'] || 'Test Settings'}</h2>
                <p>{t['testSettingsDescription'] || 'Configure test parameters'}</p>
              </div>
              
              <div className="settings-grid">
                <div className="setting-item">
                  <label>
                    <FaQuestionCircle />
                    <span>{t['questionsCount'] || 'Number of Questions'}</span>
                  </label>
                  <div className="slider-container">
                    <input
                      type="range"
                      min="20"
                      max="40"
                      value={formData.questionsCount}
                      onChange={(e) => setFormData(prev => ({ ...prev, questionsCount: parseInt(e.target.value) }))}
                      className="slider"
                    />
                    <div className="slider-value">{formData.questionsCount}</div>
                  </div>
                </div>

                <div className="setting-item">
                  <label>
                    <FaUsers />
                    <span>{t['maxParticipants'] || 'Maximum Participants'}</span>
                  </label>
                  <div className="slider-container">
                    <input
                      type="range"
                      min="2"
                      max="18"
                      value={formData.maxParticipants}
                      onChange={(e) => setFormData(prev => ({ ...prev, maxParticipants: parseInt(e.target.value) }))}
                      className="slider"
                    />
                    <div className="slider-value">{formData.maxParticipants}</div>
                  </div>
                </div>

                <div className="setting-item checkbox-setting">
                  <label className="checkbox-container">
                    <input
                      type="checkbox"
                      checked={formData.examMode}
                      onChange={(e) => setFormData(prev => ({ ...prev, examMode: e.target.checked }))}
                    />
                    <span className="checkmark"></span>
                    <div className="checkbox-content">
                      <span className="checkbox-title">{t['examMode'] || 'Exam Mode'}</span>
                      <span className="checkbox-description">
                        {t['examModeDescription'] || 'Time-limited test with results shown only at the end'}
                      </span>
                    </div>
                  </label>
                </div>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="step-section">
              <div className="step-header">
                <h2>{t['reviewSettings'] || 'Review Settings'}</h2>
                <p>{t['reviewSettingsDescription'] || 'Review your lobby configuration before creating'}</p>
              </div>
              
              <div className="review-grid">
                <div className="review-item">
                  <h3>{t['selectedCategories'] || 'Selected Categories'}</h3>
                  <div className="review-tags">
                    {formData.categories.map(catId => {
                      const category = CATEGORIES.find(c => c.id === catId);
                      return (
                        <div key={catId} className="review-tag">
                          {category?.icon}
                          <span>{category?.title}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="review-item">
                  <h3>{t['selectedSections'] || 'Selected Sections'}</h3>
                  <div className="review-count">
                    {formData.sections.length} {t['sectionsSelected'] || 'sections selected'}
                  </div>
                </div>

                <div className="review-item">
                  <h3>{t['testParameters'] || 'Test Parameters'}</h3>
                  <div className="review-params">
                    <div className="param-item">
                      <FaQuestionCircle />
                      <span>{formData.questionsCount} {t['questions'] || 'questions'}</span>
                    </div>
                    <div className="param-item">
                      <FaUsers />
                      <span>{t['upTo'] || 'Up to'} {formData.maxParticipants} {t['participants'] || 'participants'}</span>
                    </div>
                    <div className="param-item">
                      <FaCog />
                      <span>{formData.examMode ? (t['examModeOn'] || 'Exam mode ON') : (t['examModeOff'] || 'Exam mode OFF')}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Navigation buttons */}
        <div className="step-navigation">
          {step > 1 && (
            <button className="nav-btn secondary" onClick={handlePrevious}>
              <FaArrowLeft />
              {t['previous'] || 'Previous'}
            </button>
          )}
          
          <div className="nav-spacer"></div>
          
          {step < 4 ? (
            <button className="nav-btn primary" onClick={handleNext}>
              {t['next'] || 'Next'}
              <FaArrowRight />
            </button>
          ) : (
            <button 
              className={`nav-btn primary create-btn ${loading ? 'loading' : ''}`}
              onClick={handleCreateLobby}
              disabled={loading}
            >
              {loading ? (
                <div className="spinner"></div>
              ) : (
                <>
                  <FaGamepad />
                  {t['createLobby'] || 'Create Lobby'}
                </>
              )}
            </button>
          )}
        </div>
        </div>
      </div>
    </div>
  );
};

export default CreateLobbyPage; 