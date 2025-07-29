import React, { useState, useRef, useEffect } from 'react';
import { LICENSE_CATEGORIES, PDD_SECTIONS, ALLOWED_MEDIA_TYPES, API_BASE_URL } from '../../shared/config';
import LoadingSpinner from '../../shared/components/LoadingSpinner';
import ErrorDisplay from '../../shared/components/ErrorDisplay';
import ProgressBar from '../../shared/components/ProgressBar';
import { useToast, TOAST_TYPES } from '../../shared/ToastContext';
import { validateAndSanitizeFile } from '../../shared/utils/fileUtils';

const TestCreator = ({ onCreated }) => {
  // Form state
  const [questionText, setQuestionText] = useState({ ru: '', kz: '', en: '' });
  const [explanationText, setExplanationText] = useState({ ru: '', kz: '', en: '' });
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [selectedSections, setSelectedSections] = useState([]);
  const [options, setOptions] = useState([{ text: { ru: '', kz: '', en: '' } }, { text: { ru: '', kz: '', en: '' } }]);
  const [correctOptionIndex, setCorrectOptionIndex] = useState(0);
  const [media, setMedia] = useState(null);
  const [afterAnswerMedia, setAfterAnswerMedia] = useState(null);
  const [pddSearchTerm, setPddSearchTerm] = useState('');
  const [activeLanguage, setActiveLanguage] = useState('ru'); // Default language
  const fileInputRef = useRef(null);
  const afterAnswerFileInputRef = useRef(null);
  const dropzoneRef = useRef(null);
  const afterAnswerDropzoneRef = useRef(null);

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  const [compactMode, setCompactMode] = useState(true); // По умолчанию компактный режим
  const [showMediaSection, setShowMediaSection] = useState(true); // По умолчанию медиафайлы видны
  const { showToast } = useToast();
  
  // Add theme detection
  useEffect(() => {
    // Проверка и обновление темы при загрузке
    const isDarkMode = document.body.classList.contains('dark-theme');
    if (isDarkMode) {
      document.querySelector('.test-creator')?.classList.add('dark-theme-support');
      // Apply dark theme to all form elements - use a more subtle approach
      const formElements = document.querySelectorAll('.form-row, .checkbox-list, .file-input-container, .media-preview');
      formElements.forEach(el => {
        el.classList.add('dark-theme-element');
        // Don't set explicit background colors here
        el.style.backgroundColor = 'transparent';
        el.style.color = 'var(--text-light, #fff)';
        el.style.borderColor = 'var(--border-dark, #333)';
      });
      
      // Use CSS classes instead of inline styles for inputs
      // This makes the style more consistent and easier to override with CSS
      const inputElements = document.querySelectorAll('input, textarea, select');
      inputElements.forEach(el => {
        el.classList.add('dark-input');
        // Remove previous inline styles
        el.style.backgroundColor = '';
        el.style.color = '';
        el.style.borderColor = '';
      });
    } else {
      // Apply light theme to form elements
      document.querySelector('.test-creator')?.classList.remove('dark-theme-support');
      const formElements = document.querySelectorAll('.form-row, .checkbox-list, .file-input-container, .media-preview');
      formElements.forEach(el => {
        el.classList.remove('dark-theme-element');
        el.style.backgroundColor = '';
        el.style.color = '';
        el.style.borderColor = '';
      });
      
      // Remove dark input classes
      const inputElements = document.querySelectorAll('input, textarea, select');
      inputElements.forEach(el => {
        el.classList.remove('dark-input');
      });
      
      // Fix form input elements for light theme - use a more subtle approach
      const inputElements2 = document.querySelectorAll('input, textarea, select');
      inputElements2.forEach(el => {
        el.style.backgroundColor = '';
        el.style.color = '';
        el.style.borderColor = '';
      });
    }
    
    // Добавляем слушатель изменения темы на body
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          const isDark = document.body.classList.contains('dark-theme');
          if (isDark) {
            document.querySelector('.test-creator')?.classList.add('dark-theme-support');
            // Apply dark theme to all form elements
            const formElements = document.querySelectorAll('.form-row, .checkbox-list, .file-input-container, .media-preview');
            formElements.forEach(el => {
              el.classList.add('dark-theme-element');
              el.style.backgroundColor = 'transparent';
              el.style.color = 'var(--text-light, #fff)';
              el.style.borderColor = 'var(--border-dark, #333)';
            });
            
            // Use CSS classes instead of inline styles for inputs
            const inputElements = document.querySelectorAll('input, textarea, select');
            inputElements.forEach(el => {
              el.classList.add('dark-input');
              // Remove previous inline styles
              el.style.backgroundColor = '';
              el.style.color = '';
              el.style.borderColor = '';
            });
          } else {
            document.querySelector('.test-creator')?.classList.remove('dark-theme-support');
            // Remove dark theme from all form elements
            const formElements = document.querySelectorAll('.form-row, .checkbox-list, .file-input-container, .media-preview');
            formElements.forEach(el => {
              el.classList.remove('dark-theme-element');
              el.style.backgroundColor = '';
              el.style.color = '';
              el.style.borderColor = '';
            });
            
            // Remove dark input classes
            const inputElements = document.querySelectorAll('input, textarea, select');
            inputElements.forEach(el => {
              el.classList.remove('dark-input');
            });
            
            // Fix form input elements for light theme
            const inputElements2 = document.querySelectorAll('input, textarea, select');
            inputElements2.forEach(el => {
              el.style.backgroundColor = '';
              el.style.color = '';
              el.style.borderColor = '';
            });
          }
        }
      });
    });
    
    observer.observe(document.body, { attributes: true });
    
    // Log sections for debugging
    console.log('PDD_SECTIONS:', PDD_SECTIONS);
    
    return () => {
      observer.disconnect();
    };
  }, []);

  // Auto-resize textareas when language changes
  useEffect(() => {
    const textareas = document.querySelectorAll('.auto-resize');
    textareas.forEach(textarea => {
      autoResizeTextarea(textarea);
    });
  }, [activeLanguage]);
  
  // Filter PDD sections (not categories) based on search term
  const filteredPddSections = Array.isArray(PDD_SECTIONS) ? 
    PDD_SECTIONS.filter(
      section => section && typeof section === 'object' && section.title && 
      typeof section.title === 'string' && 
      section.title.toLowerCase().includes(pddSearchTerm.toLowerCase())
    ) : [];

  // Check if PDD_SECTIONS is empty and log warning
  useEffect(() => {
    if (!Array.isArray(PDD_SECTIONS) || PDD_SECTIONS.length === 0) {
      console.warn('PDD_SECTIONS is empty or not an array', PDD_SECTIONS);
    }
  }, []);

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validate form
    if (!questionText.ru.trim()) {
      showToast('Введите текст вопроса на русском языке', TOAST_TYPES.ERROR);
      setError('Введите текст вопроса на русском языке');
      return;
    }
    
    if (!questionText.kz.trim() || !questionText.en.trim()) {
      showToast('Заполните текст вопроса на всех языках', TOAST_TYPES.ERROR);
      setError('Заполните текст вопроса на всех языках');
      return;
    }
    
    // Validate options have all languages filled
    for (let i = 0; i < options.length; i++) {
      if (!options[i].text.ru.trim() || !options[i].text.kz.trim() || !options[i].text.en.trim()) {
        showToast(`Заполните вариант ${i+1} на всех языках`, TOAST_TYPES.ERROR);
        setError(`Заполните вариант ${i+1} на всех языках`);
        return;
      }
    }
    
    if (selectedCategories.length === 0) {
      showToast('Выберите хотя бы одну категорию', TOAST_TYPES.ERROR);
      setError('Выберите хотя бы одну категорию');
      return;
    }
    
    if (selectedSections.length === 0) {
      showToast('Выберите хотя бы один раздел ПДД', TOAST_TYPES.ERROR);
      setError('Выберите хотя бы один раздел ПДД');
      return;
    }
    
    if (options.length < 2) {
      showToast('Добавьте хотя бы 2 варианта ответа', TOAST_TYPES.ERROR);
      setError('Добавьте хотя бы 2 варианта ответа');
      return;
    }
    
    // Validate media file sizes (max 50MB)
    if (media && media.size > 50 * 1024 * 1024) {
      showToast('Размер основного медиа файла превышает лимит 50МБ', TOAST_TYPES.ERROR);
      setError('Размер основного медиа файла превышает лимит 50МБ');
      return;
    }
    
    if (afterAnswerMedia && afterAnswerMedia.size > 50 * 1024 * 1024) {
      showToast('Размер дополнительного медиа файла превышает лимит 50МБ', TOAST_TYPES.ERROR);
      setError('Размер дополнительного медиа файла превышает лимит 50МБ');
      return;
    }
    
    setLoading(true);
    setError(null);
    setProgress(0);
    
    try {
      // Create default explanation if empty
      const defaultExplanation = {
        ru: explanationText.ru || 'данный вопрос без объяснения',
        kz: explanationText.kz || 'бұл сұрақтың түсіндірмесі жоқ',
        en: explanationText.en || 'this question has no explanation'
      };

      // Prepare data for API with multilingual format
      const questionData = {
        question_text: questionText,
        explanation: defaultExplanation,
        options: options,
        correct_index: correctOptionIndex,
        categories: selectedCategories,
        pdd_section_uids: selectedSections,
        media_filename: media?.name || null,
        after_answer_media_filename: afterAnswerMedia?.name || null
      };
      
      // Create FormData for multipart/form-data
      const formData = new FormData();
      formData.append('question_data_str', JSON.stringify(questionData));
      
      if (media) {
        formData.append('file', media);
      }
      
      if (afterAnswerMedia) {
        formData.append('after_answer_file', afterAnswerMedia);
      }
      
      // Use XMLHttpRequest to track upload progress
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE_URL}/api/tests/`);
      xhr.withCredentials = true;
      
      // Track upload progress
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percentComplete = (event.loaded / event.total) * 100;
          setProgress(percentComplete);
        }
      };
      
      // Handle response
      xhr.onload = () => {
        setLoading(false);
        
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            if (response.success) {
              showToast('Вопрос успешно создан!', TOAST_TYPES.SUCCESS);
              resetForm();
              if (onCreated) onCreated();
            } else {
              // Даже если статус 200, но success=false, это ошибка
              const errorMessage = response.message || response.error || 'Ошибка при создании вопроса';
              console.error('Ошибка с сервера (статус 200, но success=false):', errorMessage);
              showToast(errorMessage, TOAST_TYPES.ERROR);
              setError(errorMessage);
            }
          } catch (e) {
            // Если не удалось разобрать JSON, это тоже ошибка
            console.error('Ошибка при парсинге ответа:', e, 'Текст ответа:', xhr.responseText);
            showToast('Ошибка при создании вопроса', TOAST_TYPES.ERROR);
            setError('Ошибка при создании вопроса');
          }
        } else {
          try {
            const errorResponse = JSON.parse(xhr.responseText);
            const errorMessage = errorResponse.detail || errorResponse.message || errorResponse.error || 'Ошибка при создании вопроса';
            console.error('Ошибка с сервера (статус не 2xx):', errorMessage, 'Статус:', xhr.status);
            showToast(errorMessage, TOAST_TYPES.ERROR);
            setError(errorMessage);
          } catch (e) {
            console.error('Ошибка при парсинге ответа ошибки:', e, 'Статус:', xhr.status, 'Текст ответа:', xhr.responseText);
            showToast(`Ошибка при создании вопроса (${xhr.status})`, TOAST_TYPES.ERROR);
            setError(`Ошибка при создании вопроса (${xhr.status})`);
          }
        }
      };
      
      xhr.onerror = () => {
        setLoading(false);
        const errorMessage = 'Ошибка соединения с сервером';
        console.error('Ошибка сети при создании вопроса');
        showToast(errorMessage, TOAST_TYPES.ERROR);
        setError(errorMessage);
      };
      
      xhr.ontimeout = () => {
        setLoading(false);
        const errorMessage = 'Превышено время ожидания ответа сервера';
        console.error('Таймаут при создании вопроса');
        showToast(errorMessage, TOAST_TYPES.ERROR);
        setError(errorMessage);
      };
      
      xhr.send(formData);
    } catch (err) {
      setLoading(false);
      const errorMessage = err.message || 'Произошла ошибка при создании вопроса';
      showToast(errorMessage, TOAST_TYPES.ERROR);
      setError(errorMessage);
    }
  };

  // Reset form to initial state
  const resetForm = () => {
    setQuestionText({ ru: '', kz: '', en: '' });
    setExplanationText({ ru: '', kz: '', en: '' });
    setSelectedCategories([]);
    setSelectedSections([]);
    setOptions([
      { text: { ru: '', kz: '', en: '' } }, 
      { text: { ru: '', kz: '', en: '' } }
    ]);
    setCorrectOptionIndex(0);
    setMedia(null);
    setAfterAnswerMedia(null);
    setPddSearchTerm('');
    setError(null);
    setProgress(0);
    setActiveLanguage('ru');
    
    // Clear file inputs
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    if (afterAnswerFileInputRef.current) {
      afterAnswerFileInputRef.current.value = '';
    }
  };

  // Handle question text change
  const handleQuestionTextChange = (e) => {
    setQuestionText({
      ...questionText,
      [activeLanguage]: e.target.value
    });
    // Auto-resize textarea
    autoResizeTextarea(e.target);
  };

  // Handle explanation text change
  const handleExplanationTextChange = (e) => {
    setExplanationText({
      ...explanationText,
      [activeLanguage]: e.target.value
    });
    // Auto-resize textarea
    autoResizeTextarea(e.target);
  };

  // Handle option changes
  const handleOptionChange = (index, value) => {
    const newOptions = [...options];
    newOptions[index].text = {
      ...newOptions[index].text,
      [activeLanguage]: value
    };
    setOptions(newOptions);
    // Auto-resize textarea
    const textarea = document.querySelector(`textarea[data-option-index="${index}"]`);
    if (textarea) {
      autoResizeTextarea(textarea);
    }
  };

  // Auto-resize textarea function
  const autoResizeTextarea = (textarea) => {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
  };

  // Add a new option
  const addOption = () => {
    if (options.length >= 8) {
      showToast('Максимум 8 вариантов ответа', TOAST_TYPES.WARNING);
      return;
    }
    
    setOptions([...options, { text: { ru: '', kz: '', en: '' } }]);
  };

  // Remove an option
  const removeOption = (index) => {
    if (options.length <= 2) {
      showToast('Минимум 2 варианта ответа', TOAST_TYPES.WARNING);
      return;
    }
    
    const newOptions = options.filter((_, i) => i !== index);
    setOptions(newOptions);
    
    // Adjust correct option index if needed
    if (correctOptionIndex === index) {
      setCorrectOptionIndex(0);
    } else if (correctOptionIndex > index) {
      setCorrectOptionIndex(correctOptionIndex - 1);
    }
  };

  // Handle category checkbox change
  const handleCategoryChange = (category) => {
    if (selectedCategories.includes(category)) {
      setSelectedCategories(selectedCategories.filter(cat => cat !== category));
    } else {
      setSelectedCategories([...selectedCategories, category]);
    }
  };

  // Handle section checkbox change
  const handleSectionChange = (section) => {
    if (selectedSections.includes(section)) {
      setSelectedSections(selectedSections.filter(sec => sec !== section));
    } else {
      setSelectedSections([...selectedSections, section]);
    }
  };

  // Toggle all categories
  const toggleAllCategories = () => {
    if (selectedCategories.length === LICENSE_CATEGORIES.length) {
      setSelectedCategories([]);
    } else {
      setSelectedCategories([...LICENSE_CATEGORIES]);
    }
  };

  // Handle main media file selection
  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (file) {
      try {
        const validation = validateAndSanitizeFile(file, ALLOWED_MEDIA_TYPES, 50);
        
        if (!validation.isValid) {
          showToast(validation.error, TOAST_TYPES.ERROR);
          if (fileInputRef.current) {
            fileInputRef.current.value = '';
          }
          return;
        }
        
        setMedia(validation.file);
        
        if (validation.wasRenamed) {
          showToast(
            `Файл с кириллическим именем "${validation.originalName}" переименован в "${validation.safeName}"`, 
            TOAST_TYPES.INFO
          );
        }
        
        console.log('Основной медиа файл выбран:', validation.file.name, 'Размер:', (validation.file.size / 1024 / 1024).toFixed(2), 'МБ');
      } catch (error) {
        console.error('Ошибка при обработке файла:', error);
        showToast('Ошибка при обработке файла', TOAST_TYPES.ERROR);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      }
    }
  };

  // Handle after-answer media file selection
  const handleAfterAnswerFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (file) {
      try {
        const validation = validateAndSanitizeFile(file, ALLOWED_MEDIA_TYPES, 50);
        
        if (!validation.isValid) {
          showToast(validation.error, TOAST_TYPES.ERROR);
          if (afterAnswerFileInputRef.current) {
            afterAnswerFileInputRef.current.value = '';
          }
          return;
        }
        
        setAfterAnswerMedia(validation.file);
        
        if (validation.wasRenamed) {
          showToast(
            `Дополнительный файл с кириллическим именем "${validation.originalName}" переименован в "${validation.safeName}"`, 
            TOAST_TYPES.INFO
          );
        }
        
        console.log('Дополнительный медиа файл выбран:', validation.file.name, 'Размер:', (validation.file.size / 1024 / 1024).toFixed(2), 'МБ');
      } catch (error) {
        console.error('Ошибка при обработке дополнительного файла:', error);
        showToast('Ошибка при обработке файла', TOAST_TYPES.ERROR);
        if (afterAnswerFileInputRef.current) {
          afterAnswerFileInputRef.current.value = '';
        }
      }
    }
  };

  // Handle main media drop zone events
  const handleDragOver = (e) => {
    e.preventDefault();
    if (dropzoneRef.current) {
      dropzoneRef.current.style.background = 'rgba(100, 200, 255, 0.3)';
    }
  };

  const handleDragLeave = () => {
    if (dropzoneRef.current) {
      dropzoneRef.current.style.background = 'var(--bg-secondary)';
    }
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    if (dropzoneRef.current) {
      dropzoneRef.current.style.background = 'var(--bg-secondary)';
    }
    
    const file = e.dataTransfer.files?.[0];
    if (file) {
      try {
        const validation = validateAndSanitizeFile(file, ALLOWED_MEDIA_TYPES, 50);
        
        if (!validation.isValid) {
          showToast(validation.error, TOAST_TYPES.ERROR);
          return;
        }
        
        setMedia(validation.file);
        
        if (validation.wasRenamed) {
          showToast(
            `Файл с кириллическим именем "${validation.originalName}" переименован в "${validation.safeName}"`, 
            TOAST_TYPES.INFO
          );
        }
        
        console.log('Основной медиа файл загружен через drag&drop:', validation.file.name, 'Размер:', (validation.file.size / 1024 / 1024).toFixed(2), 'МБ');
      } catch (error) {
        console.error('Ошибка при обработке файла через drag&drop:', error);
        showToast('Ошибка при обработке файла', TOAST_TYPES.ERROR);
      }
    }
  };

  // Handle after-answer media drop zone events
  const handleAfterAnswerDragOver = (e) => {
    e.preventDefault();
    if (afterAnswerDropzoneRef.current) {
      afterAnswerDropzoneRef.current.style.background = 'rgba(100, 200, 255, 0.3)';
    }
  };

  const handleAfterAnswerDragLeave = () => {
    if (afterAnswerDropzoneRef.current) {
      afterAnswerDropzoneRef.current.style.background = 'var(--bg-secondary)';
    }
  };

  const handleAfterAnswerDrop = async (e) => {
    e.preventDefault();
    if (afterAnswerDropzoneRef.current) {
      afterAnswerDropzoneRef.current.style.background = 'var(--bg-secondary)';
    }
    
    const file = e.dataTransfer.files?.[0];
    if (file) {
      try {
        const validation = validateAndSanitizeFile(file, ALLOWED_MEDIA_TYPES, 50);
        
        if (!validation.isValid) {
          showToast(validation.error, TOAST_TYPES.ERROR);
          return;
        }
        
        setAfterAnswerMedia(validation.file);
        
        if (validation.wasRenamed) {
          showToast(
            `Дополнительный файл с кириллическим именем "${validation.originalName}" переименован в "${validation.safeName}"`, 
            TOAST_TYPES.INFO
          );
        }
        
        console.log('Дополнительный медиа файл загружен через drag&drop:', validation.file.name, 'Размер:', (validation.file.size / 1024 / 1024).toFixed(2), 'МБ');
      } catch (error) {
        console.error('Ошибка при обработке дополнительного файла через drag&drop:', error);
        showToast('Ошибка при обработке файла', TOAST_TYPES.ERROR);
      }
    }
  };

  // Language selector component
  const LanguageSelector = () => (
    <div className="language-selector">
      <button
        type="button"
        className={`language-btn ${activeLanguage === 'ru' ? 'active' : ''}`}
        onClick={() => setActiveLanguage('ru')}
      >
        Русский
      </button>
      <button
        type="button"
        className={`language-btn ${activeLanguage === 'kz' ? 'active' : ''}`}
        onClick={() => setActiveLanguage('kz')}
      >
        Қазақша
      </button>
      <button
        type="button"
        className={`language-btn ${activeLanguage === 'en' ? 'active' : ''}`}
        onClick={() => setActiveLanguage('en')}
      >
        English
      </button>
    </div>
  );

  return (
    <div className="test-creator">
      <form onSubmit={handleSubmit} className="form-section">
        {/* Language selector card */}
        <div className="form-card">
          <div className="card-header">
            <h3 className="card-title">Язык ввода</h3>
          </div>
          <div className="card-content">
            <LanguageSelector />
          </div>
        </div>
        
        {/* Main content in compact layout */}
        <div className="main-content compact-layout">
          {/* Question content card */}
          <div className="form-card">
            <div className="card-header">
              <h3 className="card-title">Содержание вопроса</h3>
            </div>
            <div className="card-content">
              {/* Question text */}
              <div className="form-row">
                <label htmlFor="questionText" className="form-label">
                  Текст вопроса
                  {activeLanguage === 'ru' && <span className="required-star">*</span>}:
                </label>
                <textarea
                  id="questionText"
                  className="form-textarea auto-resize"
                  value={questionText[activeLanguage]}
                  onChange={handleQuestionTextChange}
                  placeholder={`Введите текст вопроса на ${activeLanguage === 'ru' ? 'русском' : activeLanguage === 'kz' ? 'казахском' : 'английском'} языке...`}
                  required={activeLanguage === 'ru'}
                  rows="3"
                />
              </div>

              {/* Explanation */}
              <div className="form-row">
                <label htmlFor="explanation" className="form-label">Объяснение (необязательно):</label>
                <textarea
                  id="explanation"
                  className="form-textarea auto-resize"
                  value={explanationText[activeLanguage]}
                  onChange={handleExplanationTextChange}
                  placeholder={`Введите объяснение на ${activeLanguage === 'ru' ? 'русском' : activeLanguage === 'kz' ? 'казахском' : 'английском'} языке...`}
                  rows="3"
                />
              </div>
            </div>
          </div>

          {/* Answer options card */}
          <div className="form-card">
            <div className="card-header">
              <h3 className="card-title">
                Варианты ответа
                {activeLanguage === 'ru' && <span className="required-star">*</span>}
              </h3>
            </div>
            <div className="card-content">
              <div className="options-container">
                {options.map((option, index) => (
                  <div key={index} className="option-row">
                    <input
                      type="radio"
                      name="correctOption"
                      className="option-radio"
                      checked={correctOptionIndex === index}
                      onChange={() => setCorrectOptionIndex(index)}
                    />
                    <textarea
                      className="form-textarea auto-resize option-textarea"
                      value={option.text[activeLanguage]}
                      onChange={(e) => handleOptionChange(index, e.target.value)}
                      placeholder={`Вариант ${index + 1} на ${activeLanguage === 'ru' ? 'русском' : activeLanguage === 'kz' ? 'казахском' : 'английском'} языке`}
                      required={activeLanguage === 'ru'}
                      rows="2"
                      data-option-index={index}
                    />
                    <button
                      type="button"
                      className="form-button remove-option"
                      onClick={() => removeOption(index)}
                      style={{ 
                        backgroundColor: 'var(--danger)', 
                        width: '36px', 
                        height: '36px',
                        minWidth: '36px',
                        padding: '0',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: 'var(--btn-radius)'
                      }}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                      </svg>
                    </button>
                  </div>
                ))}
                <button 
                  type="button" 
                  className="form-button" 
                  onClick={addOption}
                  style={{ backgroundColor: 'var(--accent)', color: 'white' }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
                    <line x1="12" y1="5" x2="12" y2="19"></line>
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                  </svg>
                  Добавить вариант
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Media upload card - always visible */}
        <div className="form-card">
          <div className="card-header">
            <h3 className="card-title">Медиафайлы</h3>
          </div>
          <div className="card-content">
            {/* Main Media upload */}
            <div className="form-row">
              <label className="form-label">Основной медиафайл (макс. 50 МБ):</label>
              
              {!media ? (
                <div
                  ref={dropzoneRef}
                  className="file-input-container"
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7,10 12,15 17,10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                  </svg>
                  Перетащите файл сюда или{' '}
                  <label htmlFor="media" className="file-label">
                    выберите
                  </label>
                  <input
                    ref={fileInputRef}
                    type="file"
                    id="media"
                    className="file-input"
                    accept="image/jpeg,image/png,video/mp4,video/quicktime"
                    onChange={handleFileChange}
                  />
                </div>
              ) : (
                <div className="media-preview">
                  <div className="media-container">
                    {media.type.startsWith('image') ? (
                      <img src={URL.createObjectURL(media)} alt="Preview" />
                    ) : media.type.startsWith('video') ? (
                      <video controls>
                        <source src={URL.createObjectURL(media)} type={media.type} />
                        Ваш браузер не поддерживает видео.
                      </video>
                    ) : (
                      <div className="media-placeholder">Неподдерживаемый тип файла</div>
                    )}
                  </div>
                  <div className="media-info">
                    <span className="media-name">{media.name}</span>
                    <span className="media-size">({(media.size / 1024 / 1024).toFixed(2)} МБ)</span>
                  </div>
                  <div className="media-actions">
                    <button
                      type="button"
                      className="form-button"
                      style={{ backgroundColor: 'var(--danger)', padding: '0.5rem 1rem' }}
                      onClick={() => {
                        setMedia(null);
                        if (fileInputRef.current) {
                          fileInputRef.current.value = '';
                        }
                      }}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
                        <polyline points="3,6 5,6 21,6"></polyline>
                        <path d="M19,6v14a2,2 0 0,1 -2,2H7a2,2 0 0,1 -2,-2V6m3,0V4a2,2 0 0,1 2,-2h4a2,2 0 0,1 2,2v2"></path>
                      </svg>
                      Удалить медиа
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* After-answer Media upload */}
            <div className="form-row">
              <label className="form-label">Дополнительный медиафайл для показа после ответа (макс. 50 МБ):</label>
              
              {!afterAnswerMedia ? (
                <div
                  ref={afterAnswerDropzoneRef}
                  className="file-input-container"
                  onDragOver={handleAfterAnswerDragOver}
                  onDragLeave={handleAfterAnswerDragLeave}
                  onDrop={handleAfterAnswerDrop}
                >
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7,10 12,15 17,10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                  </svg>
                  Перетащите файл сюда или{' '}
                  <label htmlFor="afterAnswerMedia" className="file-label">
                    выберите
                  </label>
                  <input
                    ref={afterAnswerFileInputRef}
                    type="file"
                    id="afterAnswerMedia"
                    className="file-input"
                    accept="image/jpeg,image/png,video/mp4,video/quicktime"
                    onChange={handleAfterAnswerFileChange}
                  />
                </div>
              ) : (
                <div className="media-preview">
                  <div className="media-container">
                    {afterAnswerMedia.type.startsWith('image') ? (
                      <img src={URL.createObjectURL(afterAnswerMedia)} alt="Preview" />
                    ) : afterAnswerMedia.type.startsWith('video') ? (
                      <video controls>
                        <source src={URL.createObjectURL(afterAnswerMedia)} type={afterAnswerMedia.type} />
                        Ваш браузер не поддерживает видео.
                      </video>
                    ) : (
                      <div className="media-placeholder">Неподдерживаемый тип файла</div>
                    )}
                  </div>
                  <div className="media-info">
                    <span className="media-name">{afterAnswerMedia.name}</span>
                    <span className="media-size">({(afterAnswerMedia.size / 1024 / 1024).toFixed(2)} МБ)</span>
                  </div>
                  <div className="media-actions">
                    <button
                      type="button"
                      className="form-button"
                      style={{ backgroundColor: 'var(--danger)', padding: '0.5rem 1rem' }}
                      onClick={() => {
                        setAfterAnswerMedia(null);
                        if (afterAnswerFileInputRef.current) {
                          afterAnswerFileInputRef.current.value = '';
                        }
                      }}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
                        <polyline points="3,6 5,6 21,6"></polyline>
                        <path d="M19,6v14a2,2 0 0,1 -2,2H7a2,2 0 0,1 -2,-2V6m3,0V4a2,2 0 0,1 2,-2h4a2,2 0 0,1 2,2v2"></path>
                      </svg>
                      Удалить медиа
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Categories and sections card - moved to bottom */}
        <div className="form-card">
          <div className="card-header">
            <h3 className="card-title">Категории и разделы</h3>
          </div>
          <div className="card-content">
            {/* License categories */}
            <div className="form-row">
              <label className="form-label">Категории:</label>
              <button
                type="button"
                className="form-button secondary"
                onClick={toggleAllCategories}
                style={{ 
                  marginBottom: '0.75rem', 
                  backgroundColor: 'var(--card-bg)', 
                  color: 'var(--main-text)', 
                  border: '1px solid var(--border-color)' 
                }}
              >
                {selectedCategories.length === LICENSE_CATEGORIES.length ? 'Отменить все' : 'Выбрать все'}
              </button>
              <div className="checkbox-list" style={{ maxHeight: '200px', overflowY: 'auto', padding: '10px', border: '1px solid var(--border-color)', borderRadius: 'var(--input-radius)' }}>
                {LICENSE_CATEGORIES.map((category) => (
                  <label key={category} className="checkbox-item">
                    <input
                      type="checkbox"
                      checked={selectedCategories.includes(category)}
                      onChange={() => handleCategoryChange(category)}
                    />
                    {category}
                  </label>
                ))}
              </div>
            </div>

            {/* PDD sections search */}
            <div className="form-row">
              <label htmlFor="pddSearch" className="form-label">Поиск по разделам ПДД:</label>
              <div className="search-input-container">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="search-icon">
                  <circle cx="11" cy="11" r="8"></circle>
                  <path d="m21 21-4.35-4.35"></path>
                </svg>
                <input
                  type="text"
                  id="pddSearch"
                  className="form-input search-input"
                  value={pddSearchTerm}
                  onChange={(e) => setPddSearchTerm(e.target.value)}
                  placeholder="Начните вводить..."
                />
              </div>
            </div>

            {/* PDD sections */}
            <div className="form-row">
              <label className="form-label">Разделы ПДД:</label>
              <div className="checkbox-list" style={{ maxHeight: '300px', overflowY: 'auto', padding: '10px', border: '1px solid var(--border-color)', borderRadius: 'var(--input-radius)' }}>
                {filteredPddSections.length > 0 ? (
                  filteredPddSections.map((section) => (
                    <label key={section.uid} className="checkbox-item">
                      <input
                        type="checkbox"
                        checked={selectedSections.includes(section.uid)}
                        onChange={() => handleSectionChange(section.uid)}
                      />
                      <span>{section.title}</span>
                    </label>
                  ))
                ) : (
                  <div>Нет соответствующих разделов</div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Progress bar */}
        {loading && (
          <div className="form-card">
            <div className="card-content">
              <div className="advanced-progress">
                <div className="progress-label">Загрузка данных на сервер</div>
                <div className="progress-bar-container">
                  <div className="progress-bar-outer">
                    <div 
                      className="progress-bar-inner" 
                      style={{ width: `${progress}%` }}
                    ></div>
                  </div>
                  <div className="progress-percentage">{Math.round(progress)}%</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error display */}
        {error && (
          <div className="form-card">
            <div className="card-content">
              <ErrorDisplay message={error} />
            </div>
          </div>
        )}

        {/* Form actions */}
        <div className="form-actions">
          <button
            type="button"
            className="form-button secondary"
            onClick={resetForm}
            disabled={loading}
            style={{ backgroundColor: 'var(--card-bg)', color: 'var(--main-text)', border: '1px solid var(--border-color)' }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
              <polyline points="1,4 1,10 7,10"></polyline>
              <path d="M3.51,15a9,9 0 1,0 2.13,-3.86L1,10"></path>
            </svg>
            Очистить
          </button>
          <button
            type="submit"
            className="form-button primary"
            disabled={loading}
            style={{ backgroundColor: 'var(--success)', color: 'white' }}
          >
            {loading ? <LoadingSpinner size="small" /> : (
              <>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                  <polyline points="22,4 12,14.01 9,11.01"></polyline>
                </svg>
                Создать вопрос
              </>
            )}
          </button>
        </div>
      </form>

      <style jsx>{`
        /* Auto-resize textarea */
        .auto-resize {
          resize: none;
          min-height: 60px;
          transition: height 0.2s ease;
          overflow-y: hidden;
          box-sizing: border-box;
        }
        
        .option-textarea {
          min-height: 50px;
          max-height: 300px;
          flex: 1;
          margin-right: 8px;
          resize: none;
        }
        
        /* Compact Layout */
        .main-content {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }
        
        .main-content.compact-layout {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
        }
        
        @media (max-width: 768px) {
          .main-content.compact-layout {
            grid-template-columns: 1fr;
          }
        }
        
        /* Card styles */
        .form-card {
          background: var(--card-bg, #ffffff);
          border: 1px solid var(--border-color, #e1e5e9);
          border-radius: 12px;
          margin-bottom: 24px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
          overflow: hidden;
          transition: all 0.2s ease;
        }
        
        .form-card:hover {
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
        }
        
        .card-header {
          background: var(--bg-secondary, #f8f9fa);
          padding: 16px 20px;
          border-bottom: 1px solid var(--border-color, #e1e5e9);
        }
        
        .card-title {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
          color: var(--main-text, #2c3e50);
        }
        
        .card-content {
          padding: 20px;
        }
        
        /* Search input styles */
        .search-input-container {
          position: relative;
          display: flex;
          align-items: center;
        }
        
        .search-icon {
          position: absolute;
          left: 12px;
          color: var(--text-muted, #6c757d);
          z-index: 1;
        }
        
        .search-input {
          padding-left: 40px !important;
        }
        
        /* Dark theme support */
        body.dark-theme .form-card {
          background: var(--card-bg-dark, #2d3748);
          border-color: var(--border-dark, #4a5568);
        }
        
        body.dark-theme .card-header {
          background: var(--bg-secondary-dark, #4a5568);
          border-color: var(--border-dark, #4a5568);
        }
        
        body.dark-theme .card-title {
          color: var(--text-light, #f7fafc);
        }
        
        /* Улучшенные стили для основного прогресс-бара */
        .advanced-progress {
          width: 100%;
          margin: 10px 0 20px;
          padding: 10px;
          background-color: var(--bg-secondary, rgba(240, 240, 240, 0.5));
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }
        
        .advanced-progress .progress-bar-outer {
          height: 12px;
          background-color: #e5e7eb;
          border-radius: 6px;
          overflow: hidden;
          margin-bottom: 5px;
          box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
          border: 1px solid #d1d5db;
        }
        
        .advanced-progress .progress-bar-inner {
          height: 100%;
          background: linear-gradient(90deg, #3b82f6 0%, #10b981 100%);
          border-radius: 6px;
          transition: width 0.3s ease;
          min-width: 2px;
        }
        
        .progress-bar-container {
          display: flex;
          align-items: center;
          width: 100%;
        }
        
        .progress-percentage {
          margin-left: 10px;
          min-width: 40px;
          text-align: right;
          font-weight: 600;
          font-size: 14px;
          color: var(--primary-color, #3498db);
        }
        
        .progress-label {
          font-size: 14px;
          font-weight: 500;
          color: var(--text-color, #333);
          margin-bottom: 8px;
          text-align: left;
        }
        
        /* Темная тема */
        body.dark-theme .advanced-progress {
          background-color: rgba(255, 255, 255, 0.05);
        }
        
        body.dark-theme .advanced-progress .progress-bar-outer {
          background-color: rgba(255, 255, 255, 0.1);
          border-color: rgba(255, 255, 255, 0.2);
        }
        
        body.dark-theme .progress-percentage {
          color: var(--accent, #2ecc71);
        }
        
        body.dark-theme .progress-label {
          color: var(--text-light, #fff);
        }
      `}</style>
    </div>
  );
};

export default TestCreator; 