// Конфигурация водяных знаков для видео
export const WATERMARK_CONFIG = {
  // Основные настройки
  text: 'Royal Test',
  
  // Видимость и стиль - делаем заметными, но не навязчивыми
  opacity: 0.3, // Увеличиваем прозрачность для видимости (было 0.15)
  fontSize: {
    min: 4, // Еще больше уменьшаем размер (было 5)
    ratio: 30 // Увеличиваем соотношение = еще меньше шрифт (было 25)
  },
  
  // Расположение - увеличиваем расстояние для меньшей кучности
  density: {
    spacing: 200 // Увеличиваем расстояние для меньшей плотности (было 150)
  },
  rotation: -45, // Угол поворота в градусах
  
  // Стиль текста
  font: {
    family: 'Arial',
    weight: 'normal', // Изменено с 'bold' на 'normal' для менее заметности
    style: 'normal'
  },
  
  // Цвета - делаем более заметными
  colors: {
    text: '#ffffff', // Основной цвет текста
    stroke: '#000000', // Цвет обводки
    strokeWidth: 0.5 // Увеличиваем обводку для видимости (было 0.2)
  },
  
  // Эффекты - увеличиваем тень для видимости
  shadow: {
    enabled: true,
    color: 'rgba(0, 0, 0, 0.4)', // Более заметная тень (было 0.2)
    blur: 0.5, // Увеличиваем размытие (было 0.3)
    offsetX: 0.3, // Увеличиваем смещение (было 0.2)
    offsetY: 0.3 // Увеличиваем смещение (было 0.2)
  },
  
  // Технические настройки
  video: {
    supportedFormats: [
      'video/mp4', // Приоритетный формат
      'video/webm;codecs=vp9',
      'video/webm'
    ]
  },
  
  // Настройки качества
  quality: {
    preserveOriginalFormat: true, // Пытаться сохранить оригинальный формат
    compressionLevel: 0.95 // Минимальное сжатие (было 0.9)
  }
};

// Функция для получения размера шрифта на основе размера видео
export const getFontSize = (videoWidth, videoHeight) => {
  const minDimension = Math.min(videoWidth, videoHeight);
  return Math.max(
    WATERMARK_CONFIG.fontSize.min, 
    minDimension / WATERMARK_CONFIG.fontSize.ratio
  );
};

// Функция для расчета количества водяных знаков - уменьшаем плотность
export const getWatermarkCount = (videoWidth, videoHeight) => {
  const area = videoWidth * videoHeight;
  const spacing = WATERMARK_CONFIG.density.spacing;
  const baseCount = Math.floor(area / (spacing * spacing));
  // Уменьшаем количество для меньшей кучности (было 2)
  return Math.max(4, Math.floor(baseCount * 1.2));
};

// Функция для получения сетки водяных знаков с лучшим распределением
export const getWatermarkGrid = (videoWidth, videoHeight) => {
  const count = getWatermarkCount(videoWidth, videoHeight);
  const gridSize = Math.sqrt(count);
  
  // Убираем боковые отступы, оставляем только верхний и нижний
  const marginX = 0; // Нет отступов по бокам - пусть вылезают
  const marginY = videoHeight * 0.02; // Минимальный отступ сверху и снизу
  
  const workingWidth = videoWidth - (marginX * 2);
  const workingHeight = videoHeight - (marginY * 2);
  
  const stepX = workingWidth / (gridSize + 1);
  const stepY = workingHeight / (gridSize + 1);
  
  return {
    gridSize: Math.ceil(gridSize),
    stepX,
    stepY,
    marginX,
    marginY
  };
}; 