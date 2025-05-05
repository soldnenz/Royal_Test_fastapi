import React, { useState, useRef } from 'react';
import { LICENSE_CATEGORIES, PDD_CATEGORIES, ALLOWED_MEDIA_TYPES, API_BASE_URL } from '../../shared/config';
import LoadingSpinner from '../../shared/components/LoadingSpinner';
import ErrorDisplay from '../../shared/components/ErrorDisplay';
import { useToast, TOAST_TYPES } from '../../shared/ToastContext';

const TestCreator = ({ onCreated }) => {
  // Form state
  const [questionText, setQuestionText] = useState({ ru: '', kz: '', en: '' });
  const [explanationText, setExplanationText] = useState({ ru: '', kz: '', en: '' });
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [selectedSections, setSelectedSections] = useState([]);
  const [options, setOptions] = useState([{ text: { ru: '', kz: '', en: '' } }, { text: { ru: '', kz: '', en: '' } }]);
  const [correctOptionIndex, setCorrectOptionIndex] = useState(0);
  const [media, setMedia] = useState(null);
  const [pddSearchTerm, setPddSearchTerm] = useState('');
  const [activeLanguage, setActiveLanguage] = useState('ru'); // Default language
  const fileInputRef = useRef(null);
  const dropzoneRef = useRef(null);

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  const { showToast } = useToast();
  
  // Filter PDD categories based on search term
  const filteredPddCategories = PDD_CATEGORIES.filter(
    cat => cat.title.toLowerCase().includes(pddSearchTerm.toLowerCase())
  );

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validate form
    if (!questionText.ru.trim()) {
      showToast('Введите текст вопроса на русском языке', TOAST_TYPES.ERROR);
      setError('Введите текст вопроса на русском языке');
      return;
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
    
    if (options.some(opt => !opt.text.ru.trim())) {
      showToast('Все варианты ответа должны быть заполнены (на русском языке)', TOAST_TYPES.ERROR);
      setError('Все варианты ответа должны быть заполнены (на русском языке)');
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
        media_filename: media?.name || null
      };
      
      // Create FormData for multipart/form-data
      const formData = new FormData();
      formData.append('question_data_str', JSON.stringify(questionData));
      
      if (media) {
        formData.append('file', media);
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
          showToast('Вопрос успешно создан!', TOAST_TYPES.SUCCESS);
          resetForm();
          if (onCreated) onCreated();
        } else {
          try {
            const errorResponse = JSON.parse(xhr.responseText);
            const errorMessage = errorResponse.detail || 'Ошибка при создании вопроса';
            showToast(errorMessage, TOAST_TYPES.ERROR);
            setError(errorMessage);
          } catch (e) {
            showToast('Ошибка при создании вопроса', TOAST_TYPES.ERROR);
            setError('Ошибка при создании вопроса');
          }
        }
      };
      
      xhr.onerror = () => {
        setLoading(false);
        const errorMessage = 'Ошибка соединения с сервером';
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
    setPddSearchTerm('');
    setError(null);
    setProgress(0);
    setActiveLanguage('ru');
    
    // Clear file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Handle question text change
  const handleQuestionTextChange = (e) => {
    setQuestionText({
      ...questionText,
      [activeLanguage]: e.target.value
    });
  };

  // Handle explanation text change
  const handleExplanationTextChange = (e) => {
    setExplanationText({
      ...explanationText,
      [activeLanguage]: e.target.value
    });
  };

  // Handle option changes
  const handleOptionChange = (index, value) => {
    const newOptions = [...options];
    newOptions[index].text = {
      ...newOptions[index].text,
      [activeLanguage]: value
    };
    setOptions(newOptions);
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

  // Handle media file selection
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (ALLOWED_MEDIA_TYPES.includes(file.type)) {
        setMedia(file);
      } else {
        showToast('Неподдерживаемый тип файла. Разрешены: JPG, PNG и MP4.', TOAST_TYPES.ERROR);
        // Clear file input
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      }
    }
  };

  // Handle drop zone events
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

  const handleDrop = (e) => {
    e.preventDefault();
    if (dropzoneRef.current) {
      dropzoneRef.current.style.background = 'var(--bg-secondary)';
    }
    
    const file = e.dataTransfer.files?.[0];
    if (file) {
      if (ALLOWED_MEDIA_TYPES.includes(file.type)) {
        setMedia(file);
        // Update file input for consistency
        if (fileInputRef.current) {
          // This is a workaround as we can't directly set files property
          const dataTransfer = new DataTransfer();
          dataTransfer.items.add(file);
          fileInputRef.current.files = dataTransfer.files;
        }
      } else {
        showToast('Неподдерживаемый тип файла. Разрешены: JPG, PNG и MP4.', TOAST_TYPES.ERROR);
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
        {/* Language selector */}
        <div className="form-row">
          <label className="form-label">Язык ввода:</label>
          <LanguageSelector />
        </div>
        
        {/* Question text */}
        <div className="form-row">
          <label htmlFor="questionText" className="form-label">
            Текст вопроса
            {activeLanguage === 'ru' && <span className="required-star">*</span>}:
          </label>
          <textarea
            id="questionText"
            className="form-textarea"
            value={questionText[activeLanguage]}
            onChange={handleQuestionTextChange}
            placeholder={`Введите текст вопроса на ${activeLanguage === 'ru' ? 'русском' : activeLanguage === 'kz' ? 'казахском' : 'английском'} языке...`}
            required={activeLanguage === 'ru'}
          />
        </div>

        {/* Explanation */}
        <div className="form-row">
          <label htmlFor="explanation" className="form-label">Объяснение (необязательно):</label>
          <textarea
            id="explanation"
            className="form-textarea"
            value={explanationText[activeLanguage]}
            onChange={handleExplanationTextChange}
            placeholder={`Введите объяснение на ${activeLanguage === 'ru' ? 'русском' : activeLanguage === 'kz' ? 'казахском' : 'английском'} языке...`}
          />
        </div>

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
          <input
            type="text"
            id="pddSearch"
            className="form-input"
            value={pddSearchTerm}
            onChange={(e) => setPddSearchTerm(e.target.value)}
            placeholder="🔍 Начните вводить..."
          />
        </div>

        {/* PDD sections */}
        <div className="form-row">
          <label className="form-label">Разделы ПДД:</label>
          <div className="checkbox-list" style={{ maxHeight: '300px', overflowY: 'auto', padding: '10px', border: '1px solid var(--border-color)', borderRadius: 'var(--input-radius)' }}>
            {filteredPddCategories.map((section) => (
              <label key={section.uid} className="checkbox-item">
                <input
                  type="checkbox"
                  checked={selectedSections.includes(section.uid)}
                  onChange={() => handleSectionChange(section.uid)}
                />
                <span>{section.title}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Answer options */}
        <div className="form-row">
          <label className="form-label">
            Варианты ответа
            {activeLanguage === 'ru' && <span className="required-star">*</span>}:
          </label>
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
                <input
                  type="text"
                  className="form-input"
                  value={option.text[activeLanguage]}
                  onChange={(e) => handleOptionChange(index, e.target.value)}
                  placeholder={`Вариант ${index + 1} на ${activeLanguage === 'ru' ? 'русском' : activeLanguage === 'kz' ? 'казахском' : 'английском'} языке`}
                  required={activeLanguage === 'ru'}
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
                  ✖
                </button>
              </div>
            ))}
            <button 
              type="button" 
              className="form-button" 
              onClick={addOption}
              style={{ backgroundColor: 'var(--accent)', color: 'white' }}
            >
              ➕ Добавить вариант
            </button>
          </div>
        </div>

        {/* Media upload */}
        <div className="form-row">
          <label className="form-label">Медиафайл:</label>
          <div
            ref={dropzoneRef}
            className="file-input-container"
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            📂 Перетащите файл сюда или{' '}
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

          {/* Media preview */}
          {media && (
            <div className="media-preview">
              {media.type.startsWith('image') ? (
                <img src={URL.createObjectURL(media)} alt="Preview" />
              ) : (
                <video src={URL.createObjectURL(media)} controls />
              )}
              <div style={{ marginTop: '0.5rem' }}>
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
                  Удалить медиа
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Progress bar */}
        {loading && (
          <div className="progress-bar">
            <div
              className="progress-bar-inner"
              style={{ width: `${progress}%` }}
            ></div>
          </div>
        )}

        {/* Error display - we keep this for additional feedback but toasts are the primary error notification */}
        {error && (
          <div className="form-row">
            <ErrorDisplay message={error} />
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
            Очистить
          </button>
          <button
            type="submit"
            className="form-button primary"
            disabled={loading}
            style={{ backgroundColor: 'var(--success)', color: 'white' }}
          >
            {loading ? <LoadingSpinner size="small" /> : '✅ Создать вопрос'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default TestCreator; 