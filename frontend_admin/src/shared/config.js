// API configuration
export const API_BASE_URL = ''; // Empty string for relative URLs

// Полный словарь разделов ПДД
export const PDD_SECTIONS = [
  {"uid":"polozheniya","title":"Общие положения"},
  {"uid":"voditeli","title":"Общие обязанности водителей"},
  {"uid":"peshehody","title":"Обязанности пешеходов"},
  {"uid":"passazhiry","title":"Обязанности пассажиров"},
  {"uid":"svetofor","title":"Сигналы светофора и регулировщика"},
  {"uid":"specsignaly","title":"Применение специальных сигналов"},
  {"uid":"avarijka","title":"Применение аварийной сигнализации и знака аварийной остановки"},
  {"uid":"manevrirovanie","title":"Маневрирование"},
  {"uid":"raspolozhenie","title":"Расположение транспортных средств на проезжей части дороги"},
  {"uid":"speed","title":"Скорость движения"},
  {"uid":"obgon","title":"Обгон, встречный разъезд"},
  {"uid":"ostanovka","title":"Остановка и стоянка"},
  {"uid":"perekrestki","title":"Проезд перекрёстков"},
  {"uid":"perehody","title":"Пешеходные переходы и остановки маршрутных транспортных средств"},
  {"uid":"zhd","title":"Движение через железнодорожные пути"},
  {"uid":"magistral","title":"Движение по автомагистралям"},
  {"uid":"zhilaya-zona","title":"Движение в жилых зонах"},
  {"uid":"prioritet","title":"Приоритет маршрутных транспортных средств"},
  {"uid":"svetovye-pribory","title":"Пользование внешними световыми приборами и звуковыми сигналами"},
  {"uid":"buksirovka","title":"Буксировка механических транспортных средств"},
  {"uid":"uchebnaya-ezda","title":"Учебная езда"},
  {"uid":"perevozka-passazhirov","title":"Перевозка пассажиров"},
  {"uid":"perevozka-gruzov","title":"Перевозка грузов"},
  {"uid":"velosipedy-i-zhivotnye","title":"Дополнительные требования к движению велосипедов, мопедов, гужевых повозок, а так же животных"},
  {"uid":"invalidy","title":"Обеспечение движения людей с нарушениями опорно-двигательного аппарата"},
  {"uid":"znaki","title":"Дорожные знаки"},
  {"uid":"razmetka","title":"Дорожная разметка и её характеристики"},
  {"uid":"dopusk","title":"Основные положения по допуску транспортных средств к эксплуатации"},
  {"uid":"obdzh","title":"ОБДЖ (Обеспечение безопасности дорожного движения)"},
  {"uid":"administrativka","title":"Административка"},
  {"uid":"medicina","title":"Медицина"},
  {"uid":"dtp","title":"ДТП"}
];

// Категории водительских прав (используются в виде массива строк)
export const PDD_CATEGORIES = ["A1", "A", "B1", "B", "BE", "C", "C1", "BC1", "D1", "D", "Tb", "CE", "DE"];

// Настройки для админ-панели
export const LICENSE_CATEGORIES = ["A1", "A", "B1", "B", "BE", "C", "C1", "BC1", "D1", "D", "Tb", "CE", "DE", "Tm"];

// Allowed media types
export const ALLOWED_MEDIA_TYPES = ["image/jpeg", "image/png", "video/mp4", "video/quicktime"];

// CSS variables for dark theme
export const DARK_THEME_COLORS = {
  background: '#1f1f1f',
  cardBackground: '#2d2d2d',
  text: '#ffffff',
  border: '#444444'
}; 