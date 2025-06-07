import React, { useState, useRef, useEffect } from 'react';
import { LICENSE_CATEGORIES, PDD_SECTIONS, ALLOWED_MEDIA_TYPES, API_BASE_URL } from '../../shared/config';
import LoadingSpinner from '../../shared/components/LoadingSpinner';
import ErrorDisplay from '../../shared/components/ErrorDisplay';
import ProgressBar from '../../shared/components/ProgressBar';
import { useToast, TOAST_TYPES } from '../../shared/ToastContext';
import { WATERMARK_CONFIG, getFontSize, getWatermarkGrid } from './watermarkConfig';

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
  const [watermarkProgress, setWatermarkProgress] = useState(0);
  const [isProcessingWatermark, setIsProcessingWatermark] = useState(false);
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

  // Add watermark to video function
  const addWatermarkToVideo = async (videoFile, onProgress = () => {}) => {
    return new Promise((resolve, reject) => {
      const video = document.createElement('video');
      video.src = URL.createObjectURL(videoFile);
      video.muted = true;
      video.crossOrigin = 'anonymous';
      video.preload = 'metadata';
      
      video.onloadedmetadata = async () => {
        // Получаем все параметры из оригинального видео
        const videoWidth = video.videoWidth;
        const videoHeight = video.videoHeight;
        const videoDuration = video.duration;
        
        // Пытаемся получить оригинальную частоту кадров, иначе используем 30 по умолчанию
        let originalFrameRate = 30;
        try {
          // Создаем VideoDecoder для получения реальных параметров видео (если поддерживается)
          if ('VideoDecoder' in window) {
            originalFrameRate = video.videoFrameRate || 30;
          }
        } catch (e) {
          console.log('Using default frame rate');
        }
        
        // Создаем canvas с точными размерами оригинального видео
        const canvas = document.createElement('canvas');
        canvas.width = videoWidth;
        canvas.height = videoHeight;
        
        const ctx = canvas.getContext('2d', { 
          alpha: false,
          colorSpace: 'srgb',
          desynchronized: true
        });
        
        // Используем конфигурацию водяных знаков
        const fontSize = getFontSize(canvas.width, canvas.height);
        const { gridSize, stepX, stepY, marginX, marginY } = getWatermarkGrid(canvas.width, canvas.height);
        
        // Определяем выходной формат
        let selectedMimeType = null;
        for (const type of WATERMARK_CONFIG.video.supportedFormats) {
          if (MediaRecorder.isTypeSupported(type)) {
            selectedMimeType = type;
            break;
          }
        }
        
        if (!selectedMimeType) {
          reject(new Error('Браузер не поддерживает запись видео'));
          return;
        }
        
        // Получаем максимально возможный битрейт для качества
        const stream = canvas.captureStream(originalFrameRate);
        
        // Рассчитываем точный битрейт оригинального видео
        const fileSizeInBits = videoFile.size * 8;
        const originalBitrate = Math.floor(fileSizeInBits / videoDuration);
        
        // Используем оригинальный битрейт с компенсацией для водяных знаков
        // +30% для компенсации дополнительных деталей от водяных знаков
        const targetBitrate = Math.floor(originalBitrate * 1.15);
        
        const mediaRecorderOptions = {
          mimeType: selectedMimeType,
          videoBitsPerSecond: targetBitrate
        };
        
        const mediaRecorder = new MediaRecorder(stream, mediaRecorderOptions);
        
        const chunks = [];
        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            chunks.push(event.data);
          }
        };
        
        mediaRecorder.onstop = () => {
          const blob = new Blob(chunks, { type: selectedMimeType });
          
          // Сохраняем оригинальное расширение файла
          const originalExtension = videoFile.name.split('.').pop().toLowerCase();
          let outputExtension = originalExtension;
          
          // Только если браузер не поддерживает mp4, используем webm
          if (originalExtension === 'mp4' && !selectedMimeType.includes('mp4')) {
            outputExtension = 'webm';
          }
          
          const watermarkedFile = new File([blob], 
            videoFile.name.replace(/\.[^/.]+$/, `_watermarked.${outputExtension}`), {
            type: selectedMimeType
          });
          resolve(watermarkedFile);
        };
        
        // Создаем водяные знаки один раз для переиспользования
        const watermarkCanvas = document.createElement('canvas');
        watermarkCanvas.width = canvas.width;
        watermarkCanvas.height = canvas.height;
        const watermarkCtx = watermarkCanvas.getContext('2d', { alpha: true });
        
        // Очищаем canvas водяных знаков
        watermarkCtx.clearRect(0, 0, watermarkCanvas.width, watermarkCanvas.height);
        
        // Настройки шрифта из конфигурации
        watermarkCtx.fillStyle = WATERMARK_CONFIG.colors.text;
        watermarkCtx.strokeStyle = WATERMARK_CONFIG.colors.stroke;
        watermarkCtx.lineWidth = WATERMARK_CONFIG.colors.strokeWidth;
        watermarkCtx.font = `${WATERMARK_CONFIG.font.weight} ${fontSize}px ${WATERMARK_CONFIG.font.family}`;
        watermarkCtx.textAlign = 'center';
        watermarkCtx.textBaseline = 'middle';
        
        // Настройки тени из конфигурации
        if (WATERMARK_CONFIG.shadow.enabled) {
          watermarkCtx.shadowColor = WATERMARK_CONFIG.shadow.color;
          watermarkCtx.shadowBlur = WATERMARK_CONFIG.shadow.blur;
          watermarkCtx.shadowOffsetX = WATERMARK_CONFIG.shadow.offsetX;
          watermarkCtx.shadowOffsetY = WATERMARK_CONFIG.shadow.offsetY;
        }
        
        // Рисуем водяные знаки один раз
        for (let i = 1; i <= gridSize; i++) {
          for (let j = 1; j <= gridSize; j++) {
            const x = marginX + stepX * i;
            const y = marginY + stepY * j;
            
            watermarkCtx.save();
            watermarkCtx.translate(x, y);
            watermarkCtx.rotate(WATERMARK_CONFIG.rotation * Math.PI / 180);
            
            // Сначала обводка, потом заливка для лучшей видимости
            if (WATERMARK_CONFIG.colors.strokeWidth > 0) {
              watermarkCtx.strokeText(WATERMARK_CONFIG.text, 0, 0);
            }
            watermarkCtx.fillText(WATERMARK_CONFIG.text, 0, 0);
            
            watermarkCtx.restore();
          }
        }
        
        // Рассчитываем точное количество кадров
        const totalFrames = Math.floor(videoDuration * originalFrameRate);
        const frameInterval = videoDuration / totalFrames;
        
        let currentFrame = 0;
        let expectedTime = 0;
        const startProcessingTime = performance.now();
        
        const processFrame = () => {
          if (currentFrame >= totalFrames) {
            mediaRecorder.stop();
            return;
          }
          
          // Точное время для текущего кадра
          const exactTime = currentFrame * frameInterval;
          video.currentTime = Math.min(exactTime, videoDuration - 0.01);
          
          video.onseeked = () => {
            // Полностью очищаем canvas
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // Устанавливаем нормальные настройки для рисования оригинального видео
            ctx.save();
            ctx.globalCompositeOperation = 'source-over';
            ctx.globalAlpha = 1.0;
            
            // Рисуем оригинальный кадр видео БЕЗ изменений
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            
            // Восстанавливаем состояние после рисования видео
            ctx.restore();
            
            // Теперь накладываем водяные знаки отдельно с их собственной прозрачностью
            ctx.save();
            ctx.globalCompositeOperation = 'source-over';
            ctx.globalAlpha = WATERMARK_CONFIG.opacity;
            ctx.drawImage(watermarkCanvas, 0, 0);
            ctx.restore();
            
            // Обновляем прогресс
            const progressPercent = (currentFrame / totalFrames) * 100;
            onProgress(progressPercent);
            
            currentFrame++;
            
            // Рассчитываем точную задержку для следующего кадра
            expectedTime += frameInterval * 1000; // переводим в миллисекунды
            const currentProcessingTime = performance.now() - startProcessingTime;
            const delay = Math.max(0, expectedTime - currentProcessingTime);
            
            setTimeout(processFrame, delay);
          };
        };
        
        // Начинаем запись и обработку
        mediaRecorder.start();
        processFrame();
      };
      
      video.onerror = () => {
        reject(new Error('Ошибка при загрузке видео'));
      };
    });
  };

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
  const handleFileChange = async (e) => {
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
        
        // Process video watermarks if it's a video file
        if (file.type.startsWith('video/')) {
          setIsProcessingWatermark(true);
          setWatermarkProgress(0);
          
          try {
            showToast('Добавление водяных знаков к видео...', TOAST_TYPES.INFO);
            
            const watermarkedFile = await addWatermarkToVideo(file, (progress) => {
              setWatermarkProgress(progress);
            });
            
            setMedia(watermarkedFile);
            showToast('Водяные знаки успешно добавлены!', TOAST_TYPES.SUCCESS);
          } catch (error) {
            console.error('Ошибка при добавлении водяных знаков:', error);
            showToast('Ошибка при добавлении водяных знаков. Используется оригинальное видео.', TOAST_TYPES.WARNING);
            setMedia(file); // Use original file if watermarking fails
          } finally {
            setIsProcessingWatermark(false);
          }
        } else {
          setMedia(file);
        }
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
  const handleAfterAnswerFileChange = async (e) => {
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
        
        // Process video watermarks if it's a video file
        if (file.type.startsWith('video/')) {
          setIsProcessingWatermark(true);
          setWatermarkProgress(0);
          
          try {
            showToast('Добавление водяных знаков к дополнительному видео...', TOAST_TYPES.INFO);
            
            const watermarkedFile = await addWatermarkToVideo(file, (progress) => {
              setWatermarkProgress(progress);
            });
            
            setAfterAnswerMedia(watermarkedFile);
            showToast('Водяные знаки успешно добавлены к дополнительному видео!', TOAST_TYPES.SUCCESS);
          } catch (error) {
            console.error('Ошибка при добавлении водяных знаков:', error);
            showToast('Ошибка при добавлении водяных знаков. Используется оригинальное видео.', TOAST_TYPES.WARNING);
            setAfterAnswerMedia(file); // Use original file if watermarking fails
          } finally {
            setIsProcessingWatermark(false);
          }
        } else {
          setAfterAnswerMedia(file);
        }
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

  const handleDrop = async (e) => {
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
        
        // Process video watermarks if it's a video file
        if (file.type.startsWith('video/')) {
          setIsProcessingWatermark(true);
          setWatermarkProgress(0);
          
          try {
            showToast('Добавление водяных знаков к видео...', TOAST_TYPES.INFO);
            
            const watermarkedFile = await addWatermarkToVideo(file, (progress) => {
              setWatermarkProgress(progress);
            });
            
            setMedia(watermarkedFile);
            showToast('Водяные знаки успешно добавлены!', TOAST_TYPES.SUCCESS);
            
            // Update file input for consistency
            if (fileInputRef.current) {
              const dataTransfer = new DataTransfer();
              dataTransfer.items.add(watermarkedFile);
              fileInputRef.current.files = dataTransfer.files;
            }
          } catch (error) {
            console.error('Ошибка при добавлении водяных знаков:', error);
            showToast('Ошибка при добавлении водяных знаков. Используется оригинальное видео.', TOAST_TYPES.WARNING);
            setMedia(file); // Use original file if watermarking fails
            
            // Update file input for consistency
            if (fileInputRef.current) {
              const dataTransfer = new DataTransfer();
              dataTransfer.items.add(file);
              fileInputRef.current.files = dataTransfer.files;
            }
          } finally {
            setIsProcessingWatermark(false);
          }
        } else {
          setMedia(file);
          // Update file input for consistency
          if (fileInputRef.current) {
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            fileInputRef.current.files = dataTransfer.files;
          }
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

  const handleAfterAnswerDrop = async (e) => {
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
        
        // Process video watermarks if it's a video file
        if (file.type.startsWith('video/')) {
          setIsProcessingWatermark(true);
          setWatermarkProgress(0);
          
          try {
            showToast('Добавление водяных знаков к дополнительному видео...', TOAST_TYPES.INFO);
            
            const watermarkedFile = await addWatermarkToVideo(file, (progress) => {
              setWatermarkProgress(progress);
            });
            
            setAfterAnswerMedia(watermarkedFile);
            showToast('Водяные знаки успешно добавлены к дополнительному видео!', TOAST_TYPES.SUCCESS);
            
            // Update file input for consistency
            if (afterAnswerFileInputRef.current) {
              const dataTransfer = new DataTransfer();
              dataTransfer.items.add(watermarkedFile);
              afterAnswerFileInputRef.current.files = dataTransfer.files;
            }
          } catch (error) {
            console.error('Ошибка при добавлении водяных знаков:', error);
            showToast('Ошибка при добавлении водяных знаков. Используется оригинальное видео.', TOAST_TYPES.WARNING);
            setAfterAnswerMedia(file); // Use original file if watermarking fails
            
            // Update file input for consistency
            if (afterAnswerFileInputRef.current) {
              const dataTransfer = new DataTransfer();
              dataTransfer.items.add(file);
              afterAnswerFileInputRef.current.files = dataTransfer.files;
            }
          } finally {
            setIsProcessingWatermark(false);
          }
        } else {
          setAfterAnswerMedia(file);
          // Update file input for consistency
          if (afterAnswerFileInputRef.current) {
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            afterAnswerFileInputRef.current.files = dataTransfer.files;
          }
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
          
          {!media ? (
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
                  Удалить медиа
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Progress bar */}
        {(loading || isProcessingWatermark) && (
          <div className="form-row">
            {loading && (
              <ProgressBar 
                progress={progress} 
                label={`Загрузка... ${Math.round(progress)}%`}
                color="var(--accent)" 
              />
            )}
            {isProcessingWatermark && (
              <ProgressBar 
                progress={watermarkProgress} 
                label={`Добавление водяных знаков... ${Math.round(watermarkProgress)}%`}
                color="var(--primary)" 
              />
            )}
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
            disabled={loading || isProcessingWatermark}
            style={{ backgroundColor: 'var(--card-bg)', color: 'var(--main-text)', border: '1px solid var(--border-color)' }}
          >
            Очистить
          </button>
          <button
            type="submit"
            className="form-button primary"
            disabled={loading || isProcessingWatermark}
            style={{ backgroundColor: 'var(--success)', color: 'white' }}
          >
            {loading || isProcessingWatermark ? <LoadingSpinner size="small" /> : '✅ Создать вопрос'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default TestCreator; 