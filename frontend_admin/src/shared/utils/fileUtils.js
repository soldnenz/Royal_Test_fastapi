/**
 * Утилиты для работы с файлами
 */

/**
 * Проверяет, содержит ли строка не-ASCII символы (включая кириллицу)
 * @param {string} str - строка для проверки
 * @returns {boolean} - true если содержит не-ASCII символы
 */
export const hasNonAsciiChars = (str) => {
  return /[^\x00-\x7F]/.test(str);
};

/**
 * Генерирует безопасное ASCII имя файла из случайных символов
 * @param {string} originalFilename - оригинальное имя файла
 * @returns {string} - безопасное имя файла
 */
export const generateSafeFilename = (originalFilename) => {
  // Генерируем случайную строку из 8 символов (цифры и буквы)
  const randomName = Array.from({ length: 8 }, () => {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    return chars.charAt(Math.floor(Math.random() * chars.length));
  }).join('');
  
  // Определяем расширение файла
  let fileExtension = 'bin'; // по умолчанию
  
  if (originalFilename && originalFilename.includes('.')) {
    const extension = originalFilename.split('.').pop().toLowerCase();
    
    // Проверяем, что расширение содержит только ASCII символы
    if (!hasNonAsciiChars(extension) && extension.length <= 10) {
      fileExtension = extension;
    }
  }
  
  return `${randomName}.${fileExtension}`;
};

/**
 * Создает новый File объект с безопасным именем если оригинальное содержит не-ASCII символы
 * @param {File} file - оригинальный файл
 * @returns {File} - файл с безопасным именем
 */
export const createSafeFile = (file) => {
  if (!file || !file.name) {
    return file;
  }
  
  // Если имя файла содержит не-ASCII символы, создаем новый файл с безопасным именем
  if (hasNonAsciiChars(file.name)) {
    const safeFilename = generateSafeFilename(file.name);
    console.log(`Файл с кириллическим именем "${file.name}" переименован в "${safeFilename}"`);
    
    // Создаем новый File объект с безопасным именем
    const safeFile = new File([file], safeFilename, {
      type: file.type,
      lastModified: file.lastModified
    });
    
    return safeFile;
  }
  
  return file;
};

/**
 * Валидирует файл и возвращает безопасную версию
 * @param {File} file - файл для валидации
 * @param {Array<string>} allowedTypes - разрешенные MIME типы
 * @param {number} maxSizeMB - максимальный размер в МБ
 * @returns {Object} - объект с результатом валидации
 */
export const validateAndSanitizeFile = (file, allowedTypes = [], maxSizeMB = 50) => {
  if (!file) {
    return { isValid: false, error: 'Файл не выбран', file: null };
  }
  
  // Проверка типа файла
  if (!file.type || file.type === '') {
    return { isValid: false, error: 'Не удалось определить тип файла', file: null };
  }
  
  if (allowedTypes.length > 0 && !allowedTypes.includes(file.type)) {
    return { 
      isValid: false, 
      error: `Неподдерживаемый тип файла. Разрешены: ${allowedTypes.join(', ')}`, 
      file: null 
    };
  }
  
  // Проверка размера файла
  if (file.size === 0) {
    return { isValid: false, error: 'Файл поврежден или пуст', file: null };
  }
  
  if (file.size > maxSizeMB * 1024 * 1024) {
    return { 
      isValid: false, 
      error: `Размер файла превышает лимит ${maxSizeMB}МБ`, 
      file: null 
    };
  }
  
  // Создаем безопасную версию файла
  const safeFile = createSafeFile(file);
  
  return { 
    isValid: true, 
    error: null, 
    file: safeFile,
    wasRenamed: safeFile.name !== file.name,
    originalName: file.name,
    safeName: safeFile.name
  };
}; 