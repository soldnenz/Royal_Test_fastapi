import React, { useState, useRef, useEffect } from 'react';
import { LICENSE_CATEGORIES, PDD_SECTIONS, ALLOWED_MEDIA_TYPES, API_BASE_URL } from '../../shared/config';
import LoadingSpinner from '../../shared/components/LoadingSpinner';
import ErrorDisplay from '../../shared/components/ErrorDisplay';
import ProgressBar from '../../shared/components/ProgressBar';
import { useToast, TOAST_TYPES } from '../../shared/ToastContext';
import axios from 'axios';
import { Modal } from 'antd';

const TestEditor = ({ onCreated, onClose, uid }) => {
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

  // Edit mode state
  const [editMode, setEditMode] = useState(false);
  const [questionId, setQuestionId] = useState(null);
  const [originalData, setOriginalData] = useState(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [isConfirmVisible, setIsConfirmVisible] = useState(false);
  const [isDataLoading, setIsDataLoading] = useState(false);
  const [mediaUrl, setMediaUrl] = useState(null);
  const [mediaType, setMediaType] = useState(null);
  const [afterAnswerMediaUrl, setAfterAnswerMediaUrl] = useState(null);
  const [afterAnswerMediaType, setAfterAnswerMediaType] = useState(null);
  const [mediaLoading, setMediaLoading] = useState(false);
  const [afterAnswerMediaLoading, setAfterAnswerMediaLoading] = useState(false);
  const [mediaLoadingProgress, setMediaLoadingProgress] = useState(0);
  const [afterAnswerMediaLoadingProgress, setAfterAnswerMediaLoadingProgress] = useState(0);
  const [removeMainMedia, setRemoveMainMedia] = useState(false);
  const [removeAfterAnswerMedia, setRemoveAfterAnswerMedia] = useState(false);
  const [replaceMainMedia, setReplaceMainMedia] = useState(false);
  const [replaceAfterAnswerMedia, setReplaceAfterAnswerMedia] = useState(false);
  const [changesList, setChangesList] = useState([]);
  const [isChangesModalVisible, setIsChangesModalVisible] = useState(false);

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  const { showToast } = useToast();
  
  // Add theme detection
  useEffect(() => {
    // Проверка и обновление темы при загрузке
    const isDarkMode = document.body.classList.contains('dark-theme');
    if (isDarkMode) {
      document.querySelector('.test-editor')?.classList.add('dark-theme-support');
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
      document.querySelector('.test-editor')?.classList.remove('dark-theme-support');
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
            document.querySelector('.test-editor')?.classList.add('dark-theme-support');
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
            document.querySelector('.test-editor')?.classList.remove('dark-theme-support');
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

  // Load test data if uid is provided
  useEffect(() => {
    if (uid) {
      setEditMode(true);
      setQuestionId(uid);
      loadTestData(uid);
    } else {
      setEditMode(false);
      setQuestionId(null);
      resetForm();
    }
  }, [uid]);

  // Load test data from API
  const loadTestData = async (testUid) => {
    setIsDataLoading(true);
    setMediaLoading(true);
    setAfterAnswerMediaLoading(true);
    setError(null);
    
    try {
      const response = await axios.get(`${API_BASE_URL}/api/tests/by_uid/${testUid}`, {
        onDownloadProgress: (progressEvent) => {
          if (progressEvent.lengthComputable) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            setMediaLoadingProgress(percentCompleted);
            setAfterAnswerMediaLoadingProgress(percentCompleted);
          }
        },
        withCredentials: true
      });
      
      const testData = response.data.data;
      setOriginalData(testData);
      
      // Set form fields
      setQuestionText(testData.question_text || { ru: '', kz: '', en: '' });
      setExplanationText(testData.explanation || { ru: '', kz: '', en: '' });
      
      // Set options and correct option
      if (testData.options && Array.isArray(testData.options)) {
        const formattedOptions = testData.options.map(opt => ({
          text: opt.text || { ru: '', kz: '', en: '' }
        }));
        setOptions(formattedOptions);
        
        // Find correct option index based on correct_label
        if (testData.correct_label) {
          const correctIndex = testData.options.findIndex(
            opt => opt.label === testData.correct_label
          );
          if (correctIndex !== -1) {
            setCorrectOptionIndex(correctIndex);
          }
        }
      }
      
      // Set categories and sections
      setSelectedCategories(testData.categories || []);
      setSelectedSections(testData.pdd_section_uids || []);
      
      // Handle media files
      if (testData.has_media && testData.media_file_base64) {
        const isVideo = testData.media_filename?.toLowerCase().endsWith('.mp4');
        const contentType = isVideo ? 'video/mp4' : 'image/jpeg';
        const dataUrl = `data:${contentType};base64,${testData.media_file_base64}`;
        setMediaUrl(dataUrl);
        setMediaType(contentType);
      }
      
      if (testData.has_after_answer_media && testData.after_answer_media_base64) {
        const isVideo = testData.after_answer_media_filename?.toLowerCase().endsWith('.mp4');
        const contentType = isVideo ? 'video/mp4' : 'image/jpeg';
        const dataUrl = `data:${contentType};base64,${testData.after_answer_media_base64}`;
        setAfterAnswerMediaUrl(dataUrl);
        setAfterAnswerMediaType(contentType);
      }
      
      setHasChanges(false);
      
    } catch (error) {
      console.error('Error loading test data:', error);
      setError('Ошибка при загрузке данных теста');
      showToast('Ошибка при загрузке данных теста', TOAST_TYPES.ERROR);
    } finally {
      setIsDataLoading(false);
      setMediaLoading(false);
      setAfterAnswerMediaLoading(false);
    }
  };
  
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

  // Detect changes in the form data
  useEffect(() => {
    if (!editMode || !originalData) return;
    
    // Массив для хранения подробных описаний изменений
    const newChangesList = [];
    
    // Сравниваем текст вопроса
    const hasTextChanges = JSON.stringify(questionText) !== JSON.stringify(originalData.question_text);
    if (hasTextChanges) {
      // Определяем, в каких языках изменился текст
      const changedLanguages = [];
      if (questionText.ru !== originalData.question_text.ru) changedLanguages.push('русском');
      if (questionText.kz !== originalData.question_text.kz) changedLanguages.push('казахском');
      if (questionText.en !== originalData.question_text.en) changedLanguages.push('английском');
      
      newChangesList.push(`Изменен текст вопроса на ${changedLanguages.join(', ')} ${changedLanguages.length > 1 ? 'языках' : 'языке'}`);
    }
    
    // Сравниваем объяснение
    const hasExplanationChanges = JSON.stringify(explanationText) !== JSON.stringify(originalData.explanation);
    if (hasExplanationChanges) {
      // Определяем, в каких языках изменилось объяснение
      const changedLanguages = [];
      if (explanationText.ru !== originalData.explanation.ru) changedLanguages.push('русском');
      if (explanationText.kz !== originalData.explanation.kz) changedLanguages.push('казахском');
      if (explanationText.en !== originalData.explanation.en) changedLanguages.push('английском');
      
      newChangesList.push(`Изменено объяснение на ${changedLanguages.join(', ')} ${changedLanguages.length > 1 ? 'языках' : 'языке'}`);
    }
    
    // Сравниваем варианты ответов
    // Сначала проверяем, изменилось ли количество вариантов
    const originalOptionsCount = originalData.options.length;
    const currentOptionsCount = options.length;
    
    if (originalOptionsCount !== currentOptionsCount) {
      if (originalOptionsCount < currentOptionsCount) {
        newChangesList.push(`Добавлено ${currentOptionsCount - originalOptionsCount} новых вариантов ответа`);
      } else {
        newChangesList.push(`Удалено ${originalOptionsCount - currentOptionsCount} вариантов ответа`);
      }
    }
    
    // Проверяем изменения в содержимом вариантов ответов
    const minOptionsLength = Math.min(originalOptionsCount, currentOptionsCount);
    for (let i = 0; i < minOptionsLength; i++) {
      const originalOption = originalData.options[i].text;
      const currentOption = options[i].text;
      
      if (JSON.stringify(originalOption) !== JSON.stringify(currentOption)) {
        // Определяем, в каких языках изменился вариант
        const changedLanguages = [];
        if (originalOption.ru !== currentOption.ru) changedLanguages.push('русском');
        if (originalOption.kz !== currentOption.kz) changedLanguages.push('казахском');
        if (originalOption.en !== currentOption.en) changedLanguages.push('английском');
        
        newChangesList.push(`Изменен вариант ответа ${i+1} на ${changedLanguages.join(', ')} ${changedLanguages.length > 1 ? 'языках' : 'языке'}`);
      }
    }
    
    // Сравниваем правильный ответ
    const originalCorrectLabel = originalData.correct_label;
    const currentCorrectLabel = originalData.options[correctOptionIndex]?.label;
    if (originalCorrectLabel !== currentCorrectLabel) {
      newChangesList.push(`Изменен правильный ответ с варианта "${originalCorrectLabel}" на вариант "${currentCorrectLabel || '?'}"`);
    }
    
    // Сравниваем категории
    const hasCategoriesChanges = JSON.stringify(selectedCategories) !== JSON.stringify(originalData.categories);
    if (hasCategoriesChanges) {
      const addedCategories = selectedCategories.filter(c => !originalData.categories.includes(c));
      const removedCategories = originalData.categories.filter(c => !selectedCategories.includes(c));
      
      if (addedCategories.length > 0) {
        newChangesList.push(`Добавлены категории: ${addedCategories.join(', ')}`);
      }
      if (removedCategories.length > 0) {
        newChangesList.push(`Удалены категории: ${removedCategories.join(', ')}`);
      }
    }
    
    // Сравниваем разделы ПДД
    const hasSectionsChanges = JSON.stringify(selectedSections) !== JSON.stringify(originalData.pdd_section_uids);
    if (hasSectionsChanges) {
      const addedSections = selectedSections.filter(s => !originalData.pdd_section_uids.includes(s));
      const removedSections = originalData.pdd_section_uids.filter(s => !selectedSections.includes(s));
      
      // Получаем названия разделов для более понятного отображения
      const getSectionTitle = (uid) => {
        const section = PDD_SECTIONS.find(s => s.uid === uid);
        return section ? section.title : uid;
      };
      
      if (addedSections.length > 0) {
        newChangesList.push(`Добавлены разделы ПДД: ${addedSections.map(getSectionTitle).join(', ')}`);
      }
      if (removedSections.length > 0) {
        newChangesList.push(`Удалены разделы ПДД: ${removedSections.map(getSectionTitle).join(', ')}`);
      }
    }
    
    // Проверяем изменения в медиа-файлах
    if (removeMainMedia) {
      newChangesList.push(`Удалено основное медиа: "${originalData.media_filename || 'Файл'}"`);
    } else if (media) {
      newChangesList.push(`Добавлено новое основное медиа: "${media.name}" (${(media.size / 1024 / 1024).toFixed(2)} МБ)`);
    }
    
    if (removeAfterAnswerMedia) {
      newChangesList.push(`Удалено дополнительное медиа: "${originalData.after_answer_media_filename || 'Файл'}"`);
    } else if (afterAnswerMedia) {
      newChangesList.push(`Добавлено новое дополнительное медиа: "${afterAnswerMedia.name}" (${(afterAnswerMedia.size / 1024 / 1024).toFixed(2)} МБ)`);
    }
    
    // Обновляем список изменений
    setChangesList(newChangesList);
    
    // Проверяем, есть ли какие-либо изменения
    setHasChanges(newChangesList.length > 0);
  }, [
    editMode, 
    originalData, 
    questionText, 
    explanationText, 
    options, 
    correctOptionIndex, 
    selectedCategories, 
    selectedSections, 
    media, 
    afterAnswerMedia,
    removeMainMedia,
    removeAfterAnswerMedia
  ]);

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Close confirmation dialog immediately when submitting
    setIsConfirmVisible(false);
    
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

      if (editMode) {
        // Edit existing question
        await handleEditSubmit(defaultExplanation);
      } else {
        // Create new question
        await handleCreateSubmit(defaultExplanation);
      }
    } catch (err) {
      setLoading(false);
      const errorMessage = err.message || 'Произошла ошибка при создании вопроса';
      showToast(errorMessage, TOAST_TYPES.ERROR);
      setError(errorMessage);
    }
  };

  // Handle edit submit
  const handleEditSubmit = async (explanation) => {
    // Prepare edit payload
    const editData = {
      question_id: questionId,
      new_question_text: questionText,
      new_explanation: explanation,
      new_options: options,
      new_correct_index: correctOptionIndex,
      new_categories: selectedCategories,
      new_pdd_section_uids: selectedSections,
      // Устанавливаем remove_media только если файл действительно существует в оригинальных данных
      remove_media: removeMainMedia && Boolean(originalData?.has_media) && Boolean(originalData?.media_file_id),
      // Устанавливаем remove_after_answer_media только если файл действительно существует в оригинальных данных
      remove_after_answer_media: removeAfterAnswerMedia && Boolean(originalData?.has_after_answer_media) && Boolean(originalData?.after_answer_media_file_id),
      // Устанавливаем replace_media только если новый файл выбран и оригинальный файл существует
      replace_media: Boolean((replaceMainMedia || media !== null) && originalData?.has_media && originalData?.media_file_id),
      // Устанавливаем replace_after_answer_media только если новый файл выбран и оригинальный файл существует
      replace_after_answer_media: Boolean((replaceAfterAnswerMedia || afterAnswerMedia !== null) && originalData?.has_after_answer_media && originalData?.after_answer_media_file_id)
    };
    
    // Create FormData for multipart/form-data
    const formData = new FormData();
    formData.append('payload', JSON.stringify(editData));
    
    if (media) {
      formData.append('new_file', media);
    }
    
    if (afterAnswerMedia) {
      formData.append('new_after_answer_file', afterAnswerMedia);
    }
    
    // Use XMLHttpRequest to track upload progress
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', `${API_BASE_URL}/api/tests/`);
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
            // Clear any existing errors first
            setError(null);
            showToast('Вопрос успешно обновлен!', TOAST_TYPES.SUCCESS);
            setHasChanges(false);
            
            // If onClose callback is provided, call it to navigate back to list
            if (onClose) {
              onClose();
            }
          } else {
            // Даже если статус 200, но success=false, это ошибка
            const errorMessage = response.message || response.error || 'Ошибка при обновлении вопроса';
            console.error('Ошибка с сервера (статус 200, но success=false):', errorMessage);
            showToast(errorMessage, TOAST_TYPES.ERROR);
            setError(errorMessage);
          }
        } catch (e) {
          // Если не удалось разобрать JSON, это тоже ошибка
          console.error('Ошибка при парсинге ответа:', e, 'Текст ответа:', xhr.responseText);
          showToast('Ошибка при обновлении вопроса', TOAST_TYPES.ERROR);
          setError('Ошибка при обновлении вопроса');
        }
      } else {
        try {
          const errorResponse = JSON.parse(xhr.responseText);
          const errorMessage = errorResponse.detail || errorResponse.message || errorResponse.error || 'Ошибка при обновлении вопроса';
          console.error('Ошибка с сервера (статус не 2xx):', errorMessage, 'Статус:', xhr.status);
          showToast(errorMessage, TOAST_TYPES.ERROR);
          setError(errorMessage);
        } catch (e) {
          console.error('Ошибка при парсинге ответа ошибки:', e, 'Статус:', xhr.status, 'Текст ответа:', xhr.responseText);
          showToast(`Ошибка при обновлении вопроса (${xhr.status})`, TOAST_TYPES.ERROR);
          setError(`Ошибка при обновлении вопроса (${xhr.status})`);
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
  };

  // Handle create submit
  const handleCreateSubmit = async (defaultExplanation) => {
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
            // Clear any errors first
            setError(null);
            showToast('Вопрос успешно создан!', TOAST_TYPES.SUCCESS);
            resetForm();
            if (onCreated) onCreated();
          } else {
            // Even with 200 status, if success=false it's an error
            const errorMessage = response.message || response.error || 'Ошибка при создании вопроса';
            console.error('Ошибка с сервера (статус 200, но success=false):', errorMessage);
            showToast(errorMessage, TOAST_TYPES.ERROR);
            setError(errorMessage);
          }
        } catch (e) {
          console.error('Ошибка при парсинге ответа:', e, 'Текст ответа:', xhr.responseText);
          showToast('Ошибка при создании вопроса', TOAST_TYPES.ERROR);
          setError('Ошибка при создании вопроса');
        }
      } else {
        try {
          const errorResponse = JSON.parse(xhr.responseText);
          const errorMessage = errorResponse.detail || 'Ошибка при создании вопроса';
          console.error('Ошибка с сервера (статус не 2xx):', errorMessage, 'Статус:', xhr.status);
          showToast(errorMessage, TOAST_TYPES.ERROR);
          setError(errorMessage);
        } catch (e) {
          console.error('Ошибка при парсинге ответа ошибки:', e, 'Статус:', xhr.status, 'Текст ответа:', xhr.responseText);
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

  // Handle main media file selection
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (ALLOWED_MEDIA_TYPES.includes(file.type)) {
        if (file.size > 50 * 1024 * 1024) {
          showToast('Размер файла превышает лимит 50МБ', TOAST_TYPES.ERROR);
          if (fileInputRef.current) {
            fileInputRef.current.value = '';
          }
          return;
        }
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

  // Handle after-answer media file selection
  const handleAfterAnswerFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (ALLOWED_MEDIA_TYPES.includes(file.type)) {
        if (file.size > 50 * 1024 * 1024) {
          showToast('Размер файла превышает лимит 50МБ', TOAST_TYPES.ERROR);
          if (afterAnswerFileInputRef.current) {
            afterAnswerFileInputRef.current.value = '';
          }
          return;
        }
        setAfterAnswerMedia(file);
      } else {
        showToast('Неподдерживаемый тип файла. Разрешены: JPG, PNG и MP4.', TOAST_TYPES.ERROR);
        // Clear file input
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

  const handleDrop = (e) => {
    e.preventDefault();
    if (dropzoneRef.current) {
      dropzoneRef.current.style.background = 'var(--bg-secondary)';
    }
    
    const file = e.dataTransfer.files?.[0];
    if (file) {
      if (ALLOWED_MEDIA_TYPES.includes(file.type)) {
        if (file.size > 50 * 1024 * 1024) {
          showToast('Размер файла превышает лимит 50МБ', TOAST_TYPES.ERROR);
          return;
        }
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

  const handleAfterAnswerDrop = (e) => {
    e.preventDefault();
    if (afterAnswerDropzoneRef.current) {
      afterAnswerDropzoneRef.current.style.background = 'var(--bg-secondary)';
    }
    
    const file = e.dataTransfer.files?.[0];
    if (file) {
      if (ALLOWED_MEDIA_TYPES.includes(file.type)) {
        if (file.size > 50 * 1024 * 1024) {
          showToast('Размер файла превышает лимит 50МБ', TOAST_TYPES.ERROR);
          return;
        }
        setAfterAnswerMedia(file);
        // Update file input for consistency
        if (afterAnswerFileInputRef.current) {
          // This is a workaround as we can't directly set files property
          const dataTransfer = new DataTransfer();
          dataTransfer.items.add(file);
          afterAnswerFileInputRef.current.files = dataTransfer.files;
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

  // Update media section for edit mode
  const renderMediaSection = () => {
    if (editMode && mediaUrl && !media && !removeMainMedia) {
      // Show existing media with loading state or preview
      return (
        <div className="media-preview">
          {mediaLoading ? (
            <div className="media-loading">
              <LoadingSpinner />
              <ProgressBar
                progress={mediaLoadingProgress}
                label={`Загрузка... ${Math.round(mediaLoadingProgress)}%`}
                color="var(--accent)"
              />
              <div>Загрузка основного медиа...</div>
            </div>
          ) : (
            <>
              <div className="media-container">
                {mediaType?.startsWith('video') ? (
                  <video controls className="detail-media">
                    <source src={mediaUrl} type={mediaType} />
                    Ваш браузер не поддерживает видео.
                  </video>
                ) : (
                  <img src={mediaUrl} alt="Превью медиа" className="detail-media" />
                )}
              </div>
              <div className="media-info">
                <span className="media-name">{originalData?.media_filename || 'Медиафайл'}</span>
              </div>
              <div className="media-actions">
                <button
                  type="button"
                  className="form-button"
                  style={{ backgroundColor: 'var(--danger)', padding: '0.5rem 1rem' }}
                  onClick={() => {
                    setRemoveMainMedia(true);
                    setMediaUrl(null);
                  }}
                >
                  Удалить медиа
                </button>
              </div>
            </>
          )}
        </div>
      );
    } else if (!media) {
      // Show upload area
      return (
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
      );
    } else {
      // Show new media preview
      return (
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
                if (editMode) {
                  setReplaceMainMedia(false);
                  if (originalData?.has_media) {
                    setMediaUrl(mediaUrl);
                    setRemoveMainMedia(false);
                  }
                }
                if (fileInputRef.current) {
                  fileInputRef.current.value = '';
                }
              }}
            >
              Удалить медиа
            </button>
          </div>
        </div>
      );
    }
  };

  // Update after-answer media section for edit mode
  const renderAfterAnswerMediaSection = () => {
    if (editMode && afterAnswerMediaUrl && !afterAnswerMedia && !removeAfterAnswerMedia) {
      // Show existing media with loading state or preview
      return (
        <div className="media-preview">
          {afterAnswerMediaLoading ? (
            <div className="media-loading">
              <LoadingSpinner />
              <ProgressBar
                progress={afterAnswerMediaLoadingProgress}
                label={`Загрузка... ${Math.round(afterAnswerMediaLoadingProgress)}%`}
                color="var(--accent)"
              />
              <div>Загрузка дополнительного медиа...</div>
            </div>
          ) : (
            <>
              <div className="media-container">
                {afterAnswerMediaType?.startsWith('video') ? (
                  <video controls className="detail-media">
                    <source src={afterAnswerMediaUrl} type={afterAnswerMediaType} />
                    Ваш браузер не поддерживает видео.
                  </video>
                ) : (
                  <img src={afterAnswerMediaUrl} alt="Превью дополнительного медиа" className="detail-media" />
                )}
              </div>
              <div className="media-info">
                <span className="media-name">{originalData?.after_answer_media_filename || 'Дополнительный медиафайл'}</span>
              </div>
              <div className="media-actions">
                <button
                  type="button"
                  className="form-button"
                  style={{ backgroundColor: 'var(--danger)', padding: '0.5rem 1rem' }}
                  onClick={() => {
                    setRemoveAfterAnswerMedia(true);
                    setAfterAnswerMediaUrl(null);
                  }}
                >
                  Удалить медиа
                </button>
              </div>
            </>
          )}
        </div>
      );
    } else if (!afterAnswerMedia) {
      // Show upload area
      return (
        <div
          ref={afterAnswerDropzoneRef}
          className="file-input-container"
          onDragOver={handleAfterAnswerDragOver}
          onDragLeave={handleAfterAnswerDragLeave}
          onDrop={handleAfterAnswerDrop}
        >
          📂 Перетащите файл сюда или{' '}
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
      );
    } else {
      // Show new media preview
      return (
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
                if (editMode) {
                  setReplaceAfterAnswerMedia(false);
                  if (originalData?.has_after_answer_media) {
                    setAfterAnswerMediaUrl(afterAnswerMediaUrl);
                    setRemoveAfterAnswerMedia(false);
                  }
                }
                if (afterAnswerFileInputRef.current) {
                  afterAnswerFileInputRef.current.value = '';
                }
              }}
            >
              Удалить медиа
            </button>
          </div>
        </div>
      );
    }
  };

  return (
    <div className={`test-editor ${editMode ? 'edit-mode' : 'create-mode'}`}>
      {/* Loading overlay */}
      {(isDataLoading || loading) && (
        <div className="loading-overlay">
          <div className="loading-content">
            <LoadingSpinner size="large" />
            <p>{isDataLoading ? 'Загрузка данных вопроса...' : 'Сохранение изменений...'}</p>
            {loading && (
              <div className="progress-container">
                <div className="progress-bar-outer">
                  <div 
                    className="progress-bar-inner" 
                    style={{ width: `${progress}%` }}
                  ></div>
                </div>
                <div className="progress-label">{Math.round(progress)}%</div>
              </div>
            )}
          </div>
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="form-section">
        {/* Header - Shows edit mode status if applicable */}
        {editMode && (
          <div className="form-row edit-mode-header">
            <h3>Редактирование вопроса #{questionId}</h3>
            {isDataLoading ? (
              <div className="loading-indicator">
                <LoadingSpinner size="small" />
                <span>Загрузка данных вопроса...</span>
              </div>
            ) : hasChanges ? (
              <div className="changes-indicator">
                <span className="warning-text">Есть несохраненные изменения</span>
                <button 
                  type="button" 
                  className="view-changes-btn"
                  onClick={() => setIsChangesModalVisible(true)}
                >
                  Просмотреть изменения
                </button>
              </div>
            ) : (
              <div className="no-changes-indicator">
                <span className="success-text">Нет изменений</span>
              </div>
            )}
          </div>
        )}
        
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
            disabled={isDataLoading}
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

        {/* Main Media upload */}
        <div className="form-row">
          <label className="form-label">Основной медиафайл (макс. 50 МБ):</label>
          
          {renderMediaSection()}
        </div>

        {/* After-answer Media upload */}
        <div className="form-row">
          <label className="form-label">Дополнительный медиафайл для показа после ответа (макс. 50 МБ):</label>
          
          {renderAfterAnswerMediaSection()}
        </div>

        {/* Progress bar */}
        {loading && (
          <div className="form-row">
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
        )}

        {/* Error display - we keep this for additional feedback but toasts are the primary error notification */}
        {error && (
          <div className="form-row">
            <ErrorDisplay message={error} />
          </div>
        )}

        {/* Form actions */}
        <div className="form-actions">
          {editMode ? (
            // Edit mode actions
            <>
              <button
                type="button"
                className="form-button secondary"
                onClick={onClose}
                disabled={loading || isDataLoading}
                style={{ backgroundColor: 'var(--card-bg)', color: 'var(--main-text)', border: '1px solid var(--border-color)' }}
              >
                Отмена
              </button>
              <button
                type="button"
                className="form-button primary"
                disabled={loading || isDataLoading || !hasChanges}
                onClick={() => setIsConfirmVisible(true)}
                style={{ backgroundColor: hasChanges ? 'var(--success)' : 'var(--disabled)', color: 'white' }}
              >
                {loading ? <LoadingSpinner size="small" /> : '✅ Сохранить изменения'}
              </button>
            </>
          ) : (
            // Create mode actions
            <>
              <button
                type="button"
                className="form-button secondary"
                onClick={resetForm}
                disabled={loading || isDataLoading}
                style={{ backgroundColor: 'var(--card-bg)', color: 'var(--main-text)', border: '1px solid var(--border-color)' }}
              >
                Очистить
              </button>
              <button
                type="submit"
                className="form-button primary"
                disabled={loading || isDataLoading}
                style={{ backgroundColor: 'var(--success)', color: 'white' }}
              >
                {loading ? <LoadingSpinner size="small" /> : '✅ Создать вопрос'}
              </button>
            </>
          )}
        </div>
      </form>

      {/* Confirmation Dialog */}
      <Modal
        title="Подтверждение изменений"
        open={isConfirmVisible}
        onOk={handleSubmit}
        onCancel={() => setIsConfirmVisible(false)}
        okText="Сохранить"
        cancelText="Отмена"
        okButtonProps={{ 
          style: { backgroundColor: 'var(--success)', borderColor: 'var(--success)' } 
        }}
      >
        <p>Вы уверены, что хотите сохранить изменения в вопросе?</p>
        <p>Все предыдущие данные будут перезаписаны.</p>
        {changesList.length > 0 && (
          <div className="changes-list">
            <h4>Список изменений:</h4>
            <ul>
              {changesList.map((change, index) => (
                <li key={index}>{change}</li>
              ))}
            </ul>
          </div>
        )}
      </Modal>

      {/* Changes List Modal */}
      <Modal
        title="Внесенные изменения"
        open={isChangesModalVisible}
        onCancel={() => setIsChangesModalVisible(false)}
        footer={[
          <button
            key="close"
            className="form-button primary"
            onClick={() => setIsChangesModalVisible(false)}
            style={{ backgroundColor: 'var(--primary)', color: 'white' }}
          >
            Закрыть
          </button>
        ]}
      >
        {changesList.length > 0 ? (
          <div className="changes-list-modal">
            <p>Вы внесли следующие изменения в вопрос:</p>
            <ul>
              {changesList.map((change, index) => (
                <li key={index}>{change}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p>Изменений не обнаружено.</p>
        )}
      </Modal>

      <style jsx>{`
        .test-editor {
          width: 100%;
          max-width: 960px;
          margin: 0 auto;
          padding: 20px;
          border-radius: 12px;
          background-color: var(--bg-color, #fff);
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
          position: relative;
          color: var(--text-color, #333);
        }
        
        .test-editor.edit-mode {
          border: 2px solid var(--warning-color, #f39c12);
        }
        
        .loading-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background-color: rgba(0, 0, 0, 0.7);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          backdrop-filter: blur(3px);
        }
        
        .loading-content {
          background-color: var(--card-bg, white);
          padding: 30px;
          border-radius: 10px;
          text-align: center;
          box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
          max-width: 80%;
          width: 400px;
          color: var(--text-color, #333);
        }
        
        .loading-content p {
          margin: 15px 0;
          font-size: 16px;
          color: var(--text-color, #333);
        }
        
        body.dark-theme .loading-content {
          background-color: var(--dark-bg, #222);
          color: var(--text-light, #fff);
        }
        
        body.dark-theme .loading-content p {
          color: var(--text-light, #fff);
        }
        
        .progress-container {
          margin: 15px 0;
          width: 100%;
        }
        
        .progress-bar-outer {
          height: 12px;
          background-color: var(--bg-secondary, #eee);
          border-radius: 6px;
          overflow: hidden;
          margin-bottom: 5px;
          box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        
        .progress-bar-inner {
          height: 100%;
          background: linear-gradient(90deg, var(--primary-color, #3498db) 0%, var(--accent, #2ecc71) 100%);
          border-radius: 6px;
          transition: width 0.3s ease;
        }
        
        .progress-label {
          font-size: 14px;
          font-weight: 500;
          color: var(--text-color, #333);
          text-align: center;
        }
        
        body.dark-theme .progress-bar-outer {
          background-color: rgba(255, 255, 255, 0.1);
        }
        
        body.dark-theme .progress-label {
          color: var(--text-light, #fff);
        }
        
        .advanced-progress {
          width: 100%;
          margin: 10px 0 20px;
          padding: 10px;
          background-color: var(--bg-secondary, rgba(240, 240, 240, 0.5));
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }
        
        .progress-bar-container {
          display: flex;
          align-items: center;
          margin-top: 8px;
        }
        
        .progress-percentage {
          margin-left: 10px;
          min-width: 40px;
          text-align: right;
          font-weight: 600;
          font-size: 14px;
          color: var(--primary-color, #3498db);
        }
        
        body.dark-theme .advanced-progress {
          background-color: rgba(255, 255, 255, 0.05);
        }
        
        body.dark-theme .progress-percentage {
          color: var(--accent, #2ecc71);
        }
        
        .edit-mode-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-bottom: 15px;
          margin-bottom: 20px;
          border-bottom: 1px solid var(--border-color, #eee);
        }
        
        .edit-mode-header h3 {
          margin: 0;
          color: var(--text-color, #333);
        }
        
        .loading-indicator {
          display: flex;
          align-items: center;
          gap: 10px;
          color: var(--primary-color, #3498db);
        }
        
        .changes-indicator {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 5px 10px;
          border-radius: 4px;
          background-color: rgba(243, 156, 18, 0.1);
        }
        
        .view-changes-btn {
          background-color: var(--primary-color, #3498db);
          color: white;
          border: none;
          padding: 5px 10px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
        }
        
        .view-changes-btn:hover {
          background-color: var(--primary-hover, #2980b9);
        }
        
        .warning-text {
          color: var(--warning-color, #f39c12);
          font-weight: 500;
        }
        
        .success-text {
          color: var(--success-color, #2ecc71);
          font-weight: 500;
        }
        
        .no-changes-indicator {
          display: flex;
          align-items: center;
          padding: 5px 10px;
          border-radius: 4px;
          background-color: rgba(46, 204, 113, 0.1);
        }
        
        .media-loading {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 20px;
          height: 200px;
          text-align: center;
        }
        
        body.dark-theme .media-loading {
          color: var(--text-light, #fff);
        }
        
        .detail-media {
          max-width: 100%;
          max-height: 300px;
          object-fit: contain;
        }
        
        .changes-list {
          margin-top: 15px;
          padding: 12px;
          background-color: var(--bg-secondary, rgba(240, 240, 240, 0.5));
          border-radius: 6px;
          border: 1px solid var(--border-color, #eee);
        }
        
        .changes-list h4 {
          margin-top: 0;
          margin-bottom: 10px;
          color: var(--primary-color, #3498db);
          font-size: 16px;
        }
        
        .changes-list ul {
          margin: 0;
          padding-left: 20px;
          color: var(--text-color, #333);
        }
        
        .changes-list li {
          margin-bottom: 8px;
          line-height: 1.4;
        }
        
        body.dark-theme .changes-list {
          background-color: rgba(255, 255, 255, 0.05);
          border-color: rgba(255, 255, 255, 0.1);
        }
        
        body.dark-theme .changes-list ul {
          color: var(--text-light, #fff);
        }
        
        .media-container {
          background-color: var(--bg-secondary, #f8f8f8);
          padding: 10px;
          border-radius: 8px;
        }
        
        body.dark-theme .media-container {
          background-color: rgba(255, 255, 255, 0.05);
        }
        
        .file-input-container {
          border: 2px dashed var(--border-color, #ddd);
          background-color: var(--bg-secondary, #f8f8f8);
          color: var(--text-color-secondary, #777);
        }
        
        body.dark-theme .file-input-container {
          border-color: rgba(255, 255, 255, 0.2);
          background-color: rgba(255, 255, 255, 0.05);
          color: var(--text-light-secondary, #bbb);
        }
        
        /* Когда страница в темной теме */
        @media (prefers-color-scheme: dark) {
          .test-editor {
            background-color: var(--dark-bg, #222);
            color: var(--text-light, #fff);
          }
          
          .media-container {
            background-color: rgba(255, 255, 255, 0.05);
          }
          
          .file-input-container {
            border-color: rgba(255, 255, 255, 0.2);
            background-color: rgba(255, 255, 255, 0.05);
            color: var(--text-light-secondary, #bbb);
          }
          
          .progress-bar-outer {
            background-color: rgba(255, 255, 255, 0.1);
          }
          
          .progress-label {
            color: var(--text-light, #fff);
          }
        }
      `}</style>
    </div>
  );
};

export default TestEditor; 