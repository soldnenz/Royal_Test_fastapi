import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';
import { translations } from '../translations/translations';
import { FaWhatsapp, FaUserGraduate, FaBuilding, FaLayerGroup, FaHandHoldingHeart } from 'react-icons/fa';

const HomePage = () => {
  const [openFaq, setOpenFaq] = useState(null);
  const { language } = useLanguage();
  const t = translations[language];

  const toggleFaq = (index) => {
    setOpenFaq(openFaq === index ? null : index);
  };

  const faqItems = [
    {
      question: t.faqCategories,
      answer: t.faqCategoriesAnswer
    },
    {
      question: t.faqFree,
      answer: t.faqFreeAnswer
    },
    {
      question: t.faqDBUpdates,
      answer: t.faqDBUpdatesAnswer
    },
    {
      question: t.faqReferral,
      answer: t.faqReferralAnswer
    },
    {
      question: t.faqMultiplayerMode,
      answer: t.faqMultiplayerModeAnswer
    }
  ];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Hero Section */}
      <section className="py-16 md:py-20 bg-gradient-to-b from-gray-50 to-white dark:from-dark-900/80 dark:to-dark-800/90">
        <div className="container-custom grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div className="flex flex-col space-y-6">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-tight text-gray-900 dark:text-white">
              {t.heroTitle}
            </h1>
            <p className="text-xl text-gray-700 dark:text-gray-300">
              {t.heroSubtitle}
            </p>
            <div className="flex flex-col sm:flex-row gap-4 pt-4">
              <Link to="/registration" className="btn-primary btn text-center">
                {t.startTesting}
              </Link>
              <a href="#how-it-works" className="button-outline btn text-center">
                {t.learnMore}
              </a>
            </div>
            <div className="flex flex-wrap gap-3 pt-2">
              <span className="px-4 py-2 bg-gray-100 dark:bg-dark-700 rounded-full text-gray-700 dark:text-gray-300 flex items-center text-sm font-medium">
                <svg className="w-5 h-5 mr-2 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                {t.currentDatabase}
              </span>
              <span className="px-4 py-2 bg-gray-100 dark:bg-dark-700 rounded-full text-gray-700 dark:text-gray-300 flex items-center text-sm font-medium">
                <svg className="w-5 h-5 mr-2 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                </svg>
                {t.highLearningSpeed}
              </span>
              <span className="px-4 py-2 bg-gray-100 dark:bg-dark-700 rounded-full text-gray-700 dark:text-gray-300 flex items-center text-sm font-medium">
                <svg className="w-5 h-5 mr-2 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                </svg>
                {t.detailedAnalytics}
              </span>
              <span className="px-4 py-2 bg-gray-100 dark:bg-dark-700 rounded-full text-gray-700 dark:text-gray-300 flex items-center text-sm font-medium">
                <svg className="w-5 h-5 mr-2 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
                </svg>
                {t.detailedAnswerExplanation}
              </span>
            </div>
          </div>
          <div className="rounded-xl overflow-hidden shadow-xl">
            <div className="bg-white dark:bg-dark-800 p-4 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700">
              <img 
                src="/images/app-interface.jpg" 
                alt={t.appInterface} 
                className="w-full h-auto rounded-lg shadow-inner"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 bg-gray-50 dark:bg-dark-900/30">
        <div className="container-custom">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4 drop-shadow-sm text-gray-900 dark:text-white">
              {language === 'kz' ? t.features : t.features} <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-primary-500">{language === 'ru' ? 'подготовиться к экзамену' : ''}</span>
            </h2>
            <p className="text-xl text-gray-700 dark:text-gray-300">
              {language === 'ru' ? 'Royal Test предлагает все необходимые инструменты для успешной сдачи экзамена ПДД с первого раза' : language === 'kz' ? 'ЖҚЕ емтиханын бірінші рет табысты тапсыру үшін барлық қажетті құралдарды ұсынады' : 'Royal Test offers all the necessary tools for successfully passing the traffic rules exam on the first try'}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <div className="card-elevated gradient-border p-8 rounded-xl">
              <div className="w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-600 rounded-lg flex items-center justify-center mb-6 shadow-lg shadow-primary-500/20">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path>
                </svg>
              </div>
              <h3 className="text-2xl font-semibold mb-3 text-gray-900 dark:text-white">{t.examSimulation}</h3>
              <p className="text-gray-700 dark:text-gray-300 mb-4">
                {language === 'ru' ? 'Воспроизводим точный формат экзаменационных билетов в ЦОН с таким же временем и системой оценки.' : t.examSimulationDesc}
              </p>
              <ul className="space-y-2 text-gray-700 dark:text-gray-300">
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-primary-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                  {t.officialTickets}
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-primary-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                  {t.timerForTest}
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-primary-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                  {t.realisticEvaluation}
                </li>
              </ul>
            </div>

            {/* Feature 2 */}
            <div className="card-elevated gradient-border p-8 rounded-xl">
              <div className="w-16 h-16 bg-gradient-to-br from-secondary-500 to-secondary-600 rounded-lg flex items-center justify-center mb-6 shadow-lg shadow-secondary-500/20">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
                </svg>
              </div>
              <h3 className="text-2xl font-semibold mb-3 text-gray-900 dark:text-white">{t.learningMode}</h3>
              <p className="text-gray-700 dark:text-gray-300 mb-4">
                {language === 'ru' ? 'Учитесь на своих ошибках с подробными объяснениями и теоретическими материалами по каждому вопросу.' : t.learningModeDesc}
              </p>
              <ul className="space-y-2 text-gray-700 dark:text-gray-300">
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-secondary-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                  {t.answerExplanation}
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-secondary-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                  {t.trafficRulesLinks}
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-secondary-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                  {t.additionalMaterials}
                </li>
              </ul>
            </div>

            {/* Feature 3 */}
            <div className="card-elevated gradient-border p-8 rounded-xl">
              <div className="w-16 h-16 bg-gradient-to-br from-accent-500 to-accent-600 rounded-lg flex items-center justify-center mb-6 shadow-lg shadow-accent-500/20">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                </svg>
              </div>
              <h3 className="text-2xl font-semibold mb-3 text-gray-900 dark:text-white">{t.statisticsProgress}</h3>
              <p className="text-gray-700 dark:text-gray-300 mb-4">
                {language === 'ru' ? 'Наглядные графики и отчеты для анализа ваших результатов и улучшения знаний' : t.statisticsProgressDesc}
              </p>
              <ul className="space-y-2 text-gray-700 dark:text-gray-300">
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-accent-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                  {t.resultsSaving}
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-accent-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                  {t.errorAnalysis}
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-accent-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                  {t.recommendationsImprovement}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="py-20 bg-gradient-to-br from-white to-gray-50 dark:from-dark-800 dark:to-dark-900/95">
        <div className="container-custom">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4 text-gray-900 dark:text-white">
              {t.howItWorks} <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-primary-500">{language === 'ru' ? 'работает' : ''}</span>
            </h2>
            <p className="text-xl text-gray-700 dark:text-gray-300 max-w-3xl mx-auto">
              {t.simpleWay}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {/* Step 1 */}
            <div className="card-elevated p-6 relative">
              <div className="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-r from-primary-500 to-primary-600 rounded-full flex items-center justify-center shadow-lg shadow-primary-500/20 z-10">
                <span className="text-white font-bold text-xl">1</span>
              </div>
              <h3 className="text-xl font-bold mt-4 mb-3 text-gray-900 dark:text-white">{t.registration}</h3>
              <p className="text-gray-700 dark:text-gray-300">
                {t.registrationDesc}
              </p>
            </div>

            {/* Step 2 */}
            <div className="card-elevated p-6 relative">
              <div className="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-r from-primary-500 to-primary-600 rounded-full flex items-center justify-center shadow-lg shadow-primary-500/20 z-10">
                <span className="text-white font-bold text-xl">2</span>
              </div>
              <h3 className="text-xl font-bold mt-4 mb-3 text-gray-900 dark:text-white">{t.choosePackage}</h3>
              <p className="text-gray-700 dark:text-gray-300">
                {t.choosePackageDesc}
              </p>
            </div>

            {/* Step 3 */}
            <div className="card-elevated p-6 relative">
              <div className="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-r from-primary-500 to-primary-600 rounded-full flex items-center justify-center shadow-lg shadow-primary-500/20 z-10">
                <span className="text-white font-bold text-xl">3</span>
              </div>
              <h3 className="text-xl font-bold mt-4 mb-3 text-gray-900 dark:text-white">{t.payment}</h3>
              <p className="text-gray-700 dark:text-gray-300">
                {t.paymentDesc}
              </p>
            </div>

            {/* Step 4 */}
            <div className="card-elevated p-6 relative">
              <div className="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-r from-primary-500 to-primary-600 rounded-full flex items-center justify-center shadow-lg shadow-primary-500/20 z-10">
                <span className="text-white font-bold text-xl">4</span>
              </div>
              <h3 className="text-xl font-bold mt-4 mb-3 text-gray-900 dark:text-white">{t.enjoy}</h3>
              <p className="text-gray-700 dark:text-gray-300">
                {t.enjoyDesc}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Categories Section */}
      <section id="categories" className="py-20 bg-gradient-to-br from-gray-50 to-white dark:from-dark-900 dark:to-dark-800">
        <div className="container-custom">
          <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-bold mb-4 text-gray-900 dark:text-white">
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-primary-500">{t.categoriesTitle}</span>
              </h2>
              <p className="text-xl text-gray-700 dark:text-gray-300 max-w-3xl mx-auto">
                {t.categoriesSubtitle}
              </p>
            </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {/* PDD Category */}
            <div className="group bg-white dark:bg-dark-800 rounded-xl shadow-md hover:shadow-xl transition-all duration-300 transform hover:-translate-y-2 relative p-6">
              <div className="flex items-center mb-4">
                <div className="flex items-center justify-center h-12 w-12 rounded-lg bg-primary-100 dark:bg-primary-900/30 text-primary-600 mr-4">
                  <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-white">{t.pddAllSections}</h3>
              </div>
              <p className="text-gray-700 dark:text-gray-300 ml-16">
                {t.pddAllSectionsDesc}
              </p>
            </div>

            {/* Medical Category */}
            <div className="group bg-white dark:bg-dark-800 rounded-xl shadow-md hover:shadow-xl transition-all duration-300 transform hover:-translate-y-2 relative p-6">
              <div className="flex items-center mb-4">
                <div className="flex items-center justify-center h-12 w-12 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-600 mr-4">
                  <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-white">{t.medicalPrepare}</h3>
              </div>
              <p className="text-gray-700 dark:text-gray-300 ml-16">
                {t.medicalPrepareDesc}
              </p>
            </div>

            {/* Fines Category */}
            <div className="group bg-white dark:bg-dark-800 rounded-xl shadow-md hover:shadow-xl transition-all duration-300 transform hover:-translate-y-2 relative p-6">
              <div className="flex items-center mb-4">
                <div className="flex items-center justify-center h-12 w-12 rounded-lg bg-orange-100 dark:bg-orange-900/30 text-orange-600 mr-4">
                  <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"></path>
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-white">{t.finesPunishments}</h3>
              </div>
              <p className="text-gray-700 dark:text-gray-300 ml-16">
                {t.finesPunishmentsDesc}
              </p>
            </div>

            {/* Road Signs Category */}
            <div className="group bg-white dark:bg-dark-800 rounded-xl shadow-md hover:shadow-xl transition-all duration-300 transform hover:-translate-y-2 relative p-6">
              <div className="flex items-center mb-4">
                <div className="flex items-center justify-center h-12 w-12 rounded-lg bg-blue-100 dark:bg-blue-900/30 text-blue-600 mr-4">
                  <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-white">{t.roadSigns}</h3>
              </div>
              <p className="text-gray-700 dark:text-gray-300 ml-16">
                {t.roadSignsDesc}
              </p>
            </div>

            {/* Maneuvers Category */}
            <div className="group bg-white dark:bg-dark-800 rounded-xl shadow-md hover:shadow-xl transition-all duration-300 transform hover:-translate-y-2 relative p-6">
              <div className="flex items-center mb-4">
                <div className="flex items-center justify-center h-12 w-12 rounded-lg bg-purple-100 dark:bg-purple-900/30 text-purple-600 mr-4">
                  <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M13 9l3 3m0 0l-3 3m3-3H8m13 0a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-white">{t.maneuversCrossroads}</h3>
              </div>
              <p className="text-gray-700 dark:text-gray-300 ml-16">
                {t.maneuversCrossroadsDesc}
              </p>
            </div>

            {/* Special Transport Category */}
            <div className="group bg-white dark:bg-dark-800 rounded-xl shadow-md hover:shadow-xl transition-all duration-300 transform hover:-translate-y-2 relative p-6">
              <div className="flex items-center mb-4">
                <div className="flex items-center justify-center h-12 w-12 rounded-lg bg-green-100 dark:bg-green-900/30 text-green-600 mr-4">
                  <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path>
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-white">{t.specialTransport}</h3>
              </div>
              <p className="text-gray-700 dark:text-gray-300 ml-16">
                {t.specialTransportDesc}
              </p>
            </div>

            {/* Drones Category - Coming Soon */}
            <div className="group bg-white dark:bg-dark-800 rounded-xl shadow-md relative p-6">
              <div className="absolute top-3 right-3">
                <span className="bg-primary-500 text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider shadow-sm">{t.comingSoonSection}</span>
              </div>
              <div className="flex items-center mb-4">
                <div className="flex items-center justify-center h-12 w-12 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-500 mr-4">
                  <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"></path>
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-gray-400 dark:text-gray-500">{t.drones}</h3>
              </div>
              <p className="text-gray-500 dark:text-gray-400 ml-16">
                {t.dronesDesc}
              </p>
              <p className="mt-4 text-sm text-gray-500 dark:text-gray-400 italic ml-16">
                {t.inDevelopment}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Features Details */}
      <section className="py-16 bg-gradient-to-br from-white to-gray-50 dark:from-dark-800 dark:to-dark-900">
        <div className="container-custom">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-12 text-gray-900 dark:text-white drop-shadow-sm">
            {t.specialFeatures}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            <div className="card-elevated hover-lift">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary-100 to-primary-200 dark:from-primary-900/30 dark:to-primary-800/30 flex items-center justify-center mb-4 shadow-sm">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">{t.currentDatabase}</h3>
              <p className="text-gray-800 dark:text-gray-300">
                {t.currentDatabaseDesc}
              </p>
            </div>

            <div className="card-elevated hover-lift">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-secondary-100 to-secondary-200 dark:from-secondary-900/30 dark:to-secondary-800/30 flex items-center justify-center mb-4 shadow-sm">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-secondary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">{t.multiplayer}</h3>
              <p className="text-gray-800 dark:text-gray-300">
                {t.multiplayerDesc}
              </p>
            </div>

            <div className="bg-white/90 dark:bg-dark-800/90 backdrop-blur-sm rounded-xl p-6 shadow-lg border border-gray-200 dark:border-gray-700 flex flex-col hover:-translate-y-1 hover:shadow-xl transition-all duration-300">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-accent-100 to-accent-200 dark:from-accent-900/30 dark:to-accent-800/30 flex items-center justify-center mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="size-6">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 0 0 6 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0 1 18 16.5h-2.25m-7.5 0h7.5m-7.5 0-1 3m8.5-3 1 3m0 0 .5 1.5m-.5-1.5h-9.5m0 0-.5 1.5m.75-9 3-3 2.148 2.148A12.061 12.061 0 0 1 16.5 7.605" />
            </svg>
              </div>
              <h3 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">{t.detailedExplanations}</h3>
              <p className="text-gray-800 dark:text-gray-300">
                {t.detailedExplanationsDesc}
              </p>
            </div>

            <div className="bg-white/90 dark:bg-dark-800/90 backdrop-blur-sm rounded-xl p-6 shadow-lg border border-gray-200 dark:border-gray-700 flex flex-col hover:-translate-y-1 hover:shadow-xl transition-all duration-300">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary-100 to-primary-200 dark:from-primary-900/30 dark:to-primary-800/30 flex items-center justify-center mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">{t.gamification}</h3>
              <p className="text-gray-800 dark:text-gray-300">
                {t.gamificationDesc} <span className="text-xs text-primary-500">{t.comingSoon}</span>
              </p>
            </div>

            <div className="bg-white/90 dark:bg-dark-800/90 backdrop-blur-sm rounded-xl p-6 shadow-lg border border-gray-200 dark:border-gray-700 flex flex-col hover:-translate-y-1 hover:shadow-xl transition-all duration-300">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-secondary-100 to-secondary-200 dark:from-secondary-900/30 dark:to-secondary-800/30 flex items-center justify-center mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-secondary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">{t.statisticsProgress}</h3>
              <p className="text-gray-800 dark:text-gray-300">
                {language === 'kz' ? t.statisticsProgressDesc : 'Наглядные графики и отчеты для анализа ваших результатов и улучшения знаний'}
              </p>
            </div>

            <div className="bg-white/90 dark:bg-dark-800/90 backdrop-blur-sm rounded-xl p-6 shadow-lg border border-gray-200 dark:border-gray-700 flex flex-col hover:-translate-y-1 hover:shadow-xl transition-all duration-300">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-accent-100 to-accent-200 dark:from-accent-900/30 dark:to-accent-800/30 flex items-center justify-center mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-accent-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">{t.referralSystem}</h3>
              <p className="text-gray-800 dark:text-gray-300">
                {language === 'kz' ? 'Достарыңызды шақырыңыз және жазылымның бонустық күндері мен артықшылықтарын алыңыз' : 'Приглашайте друзей и получайте бонусные дни подписки и преимущества'}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-20 bg-gradient-to-br from-gray-50 to-white dark:from-dark-900 dark:to-dark-800">
        <div className="container-custom">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4 text-gray-900 dark:text-white">
              {language === 'kz' ? t.flexibleTariffs : language === 'en' ? 'Flexible' : 'Гибкие'} <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-primary-500">{language === 'ru' ? 'тарифы' : language === 'kz' ? t.tariffs : 'tariffs'}</span> {language === 'ru' ? 'для любого формата обучения' : language === 'kz' ? '' : 'for any learning format'}
            </h2>
            <p className="text-xl text-gray-700 dark:text-gray-300 max-w-3xl mx-auto">
              {language === 'kz' ? t.choosePlanSubtitle : language === 'en' ? 'Choose a plan that suits you. All tariff plans include full access to the question database and results analytics.' : 'Выберите план, который подходит именно вам. Все тарифные планы включают полный доступ к базе вопросов и аналитике результатов.'}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Economy Plan */}
            <div className="rounded-2xl overflow-hidden bg-white dark:bg-dark-800 shadow-xl hover:shadow-2xl transition-all duration-300 border border-gray-100 dark:border-dark-700 relative flex flex-col h-full transform hover:-translate-y-1">
              <div className="h-3 bg-gray-200 dark:bg-gray-700"></div>
              <div className="p-8 flex-grow">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2 flex items-center">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 mr-2 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {t.economyTitle}
                </h3>
                <div className="flex items-end mb-6 mt-4">
                  <span className="text-4xl font-bold text-gray-800 dark:text-white">{t.economyPrice}</span>
                  <span className="text-lg text-gray-600 dark:text-gray-400 ml-1">{t.perMonth}</span>
                </div>
                <div className="bg-gray-50 dark:bg-dark-700/50 p-4 rounded-lg mb-6">
                  <ul className="space-y-4">
                    <li className="flex items-start">
                      <svg className="w-5 h-5 text-green-500 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                      </svg>
                      <span className="text-gray-700 dark:text-gray-300">{t.accessToCategories}</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 text-green-500 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                      </svg>
                      <span className="text-gray-700 dark:text-gray-300">{t.fullQuestionDatabase}</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 text-green-500 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                      </svg>
                      <span className="text-gray-700 dark:text-gray-300">{t.accessBasicStats}</span>
                    </li>
                    <li className="flex items-start text-gray-400">
                      <svg className="w-5 h-5 text-gray-300 dark:text-gray-600 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                      </svg>
                      <span className="text-gray-400 dark:text-gray-500">{t.referralProgram}</span>
                    </li>
                    <li className="flex items-start text-gray-400">
                      <svg className="w-5 h-5 text-gray-300 dark:text-gray-600 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                      </svg>
                      <span className="text-gray-400 dark:text-gray-500">{t.lobbyCreation}</span>
                    </li>
                  </ul>
                </div>
                <div className="mt-auto">
                  <Link to="/registration" className="w-full py-3 px-6 text-center rounded-lg border-2 border-gray-400 text-gray-600 font-bold hover:bg-gray-50 dark:hover:bg-dark-700 transition-colors duration-200 inline-block">
                    {language === 'ru' ? 'Выбрать' : language === 'kz' ? 'Таңдау' : 'Choose'}
                  </Link>
                </div>
              </div>
            </div>

            {/* VIP Plan */}
            <div className="rounded-2xl overflow-hidden bg-white dark:bg-dark-800 shadow-2xl transition-all duration-300 border-2 border-primary-500 dark:border-primary-500 relative flex flex-col h-full transform hover:-translate-y-1 z-10 scale-105">
              <div className="absolute top-0 right-0">
                <div className="bg-primary-500 text-white text-xs font-bold px-4 py-1 rounded-bl-lg">
                  {t.popular}
                </div>
              </div>
              <div className="h-3 bg-gradient-to-r from-primary-400 to-primary-600"></div>
              <div className="p-8 flex-grow">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2 flex items-center">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7 mr-2 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                  {t.vipTitle}
                </h3>
                <div className="flex items-end mb-6 mt-4">
                  <span className="text-4xl font-bold text-primary-600">{t.vipPrice}</span>
                  <span className="text-lg text-gray-600 dark:text-gray-400 ml-1">{t.perMonth}</span>
                </div>
                <div className="bg-gradient-to-br from-primary-50 to-white dark:from-primary-900/20 dark:to-dark-800/70 p-4 rounded-lg mb-6 border border-primary-100 dark:border-primary-800/30">
                  <ul className="space-y-4">
                    <li className="flex items-start">
                      <svg className="w-5 h-5 text-primary-600 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                      </svg>
                      <span className="text-gray-800 dark:text-gray-200 font-medium">{t.accessAllCats}</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 text-primary-600 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                      </svg>
                      <span className="text-gray-800 dark:text-gray-200">{t.createRefLink}</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 text-primary-600 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                      </svg>
                      <span className="text-gray-800 dark:text-gray-200">{t.accessFullStats}</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 text-primary-600 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                      </svg>
                      <span className="text-gray-800 dark:text-gray-200">{t.giftTestsToFriends}</span>
                    </li>
                    <li className="flex items-start text-gray-400">
                      <svg className="w-5 h-5 text-gray-300 dark:text-gray-600 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                      </svg>
                      <span className="text-gray-400 dark:text-gray-500">{t.createLobby}</span>
                    </li>
                  </ul>
                </div>
                <div className="mt-auto">
                  <Link to="/registration" className="w-full py-3 px-6 text-center rounded-lg bg-gradient-to-r from-primary-500 to-primary-600 text-white font-bold hover:from-primary-600 hover:to-primary-700 transition-all duration-200 inline-block shadow-md hover:shadow-lg">
                    {language === 'ru' ? 'Выбрать' : language === 'kz' ? 'Таңдау' : 'Choose'}
                  </Link>
                </div>
              </div>
            </div>

            {/* Royal Plan */}
            <div className="rounded-2xl overflow-hidden bg-white dark:bg-dark-800 shadow-xl hover:shadow-2xl transition-all duration-300 border-2 border-orange-400 dark:border-orange-500/50 relative flex flex-col h-full transform hover:-translate-y-1">
              <div className="h-3 bg-gradient-to-r from-orange-400 via-amber-500 to-yellow-400"></div>
              <div className="p-8 flex-grow">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2 flex items-center">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-7 w-7 mr-2 text-yellow-500">
                    <path d="M11.584 2.376a.75.75 0 01.832 0l9 6a.75.75 0 11-.832 1.248L12 3.901 3.416 9.624a.75.75 0 01-.832-1.248l9-6z" />
                    <path fillRule="evenodd" d="M20.25 10.332v9.918H21a.75.75 0 010 1.5H3a.75.75 0 010-1.5h.75v-9.918a.75.75 0 01.634-.74A49.109 49.109 0 0112 9c2.59 0 5.134.175 7.616.514a.75.75 0 01.634.738zm-7.5 2.418a.75.75 0 00-1.5 0v6.75a.75.75 0 001.5 0v-6.75zm3-.75a.75.75 0 01.75.75v6.75a.75.75 0 01-1.5 0v-6.75a.75.75 0 01.75-.75zM9 12.75a.75.75 0 00-1.5 0v6.75a.75.75 0 001.5 0v-6.75z" clipRule="evenodd" />
                    <path d="M12 7.875a1.125 1.125 0 100-2.25 1.125 1.125 0 000 2.25z" />
                  </svg>
                  {t.royalTitle}
                </h3>
                <div className="flex items-end mb-6 mt-4">
                  <span className="text-4xl font-bold text-orange-600 dark:text-orange-500">{t.royalPrice}</span>
                  <span className="text-lg text-gray-600 dark:text-gray-400 ml-1">{t.perMonth}</span>
                </div>
                <div className="bg-gradient-to-br from-orange-50 via-amber-50 to-white dark:from-orange-900/20 dark:via-amber-900/10 dark:to-dark-800/70 p-4 rounded-lg mb-6 border border-orange-200 dark:border-orange-800/30">
                  <ul className="space-y-4">
                    <li className="flex items-start">
                      <svg className="w-5 h-5 text-orange-600 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                      </svg>
                      <span className="text-gray-800 dark:text-gray-200 font-medium">{t.accessAllCats}</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 text-orange-600 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                      </svg>
                      <span className="text-gray-800 dark:text-gray-200">{t.createRefLink}</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 text-orange-600 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                      </svg>
                      <span className="text-gray-800 dark:text-gray-200">{t.accessFullStats}</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 text-orange-600 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                      </svg>
                      <span className="text-gray-800 dark:text-gray-200">{t.createLobby}</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 text-orange-600 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                      </svg>
                      <span className="text-gray-800 dark:text-gray-200">{t.giftTestsGroupCodes}</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 text-orange-600 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                      </svg>
                      <span className="text-gray-800 dark:text-gray-200">{t.discount15}</span>
                    </li>
                  </ul>
                </div>
                <div className="mt-auto">
                  <Link to="/registration" className="w-full py-3 px-6 text-center rounded-lg bg-gradient-to-r from-orange-500 via-amber-500 to-yellow-500 text-white font-bold hover:from-orange-600 hover:via-amber-600 hover:to-yellow-600 transition-all duration-200 inline-block shadow-md hover:shadow-lg">
                    {language === 'ru' ? 'Выбрать' : language === 'kz' ? 'Таңдау' : 'Choose'}
                  </Link>
                </div>
              </div>
            </div>
          </div>

          {/* Additional Features */}
          <div className="mt-16 bg-white dark:bg-dark-800 shadow-lg rounded-xl overflow-hidden border border-gray-100 dark:border-dark-700">
            <div className="p-8">
              <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">{t.additionalFeatures}</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Feature 1 */}
                <div className="bg-gray-50 dark:bg-dark-700/50 p-5 rounded-lg border border-gray-200 dark:border-gray-700 hover:shadow-md transition-all">
                  <div className="flex items-start">
                    <div className="mr-4 flex-shrink-0">
                      <div className="w-12 h-12 rounded-lg bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-600 dark:text-primary-400">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7"></path>
                        </svg>
                      </div>
                    </div>
                    <div>
                      <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">{t.giftAccess}</h4>
                      <p className="text-gray-600 dark:text-gray-400">
                        {t.giftAccessDesc}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Feature 2 */}
                <div className="bg-gray-50 dark:bg-dark-700/50 p-5 rounded-lg border border-gray-200 dark:border-gray-700 hover:shadow-md transition-all">
                  <div className="flex items-start">
                    <div className="mr-4 flex-shrink-0">
                      <div className="w-12 h-12 rounded-lg bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-600 dark:text-primary-400">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z"></path>
                        </svg>  
                      </div>
                    </div>
                    <div>
                      <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">{t.groupPromocodes}</h4>
                      <p className="text-gray-600 dark:text-gray-400">
                        {t.groupPromocodesDesc}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Feature 3 */}
                <div className="bg-gray-50 dark:bg-dark-700/50 p-5 rounded-lg border border-gray-200 dark:border-gray-700 hover:shadow-md transition-all">
                  <div className="flex items-start">
                    <div className="mr-4 flex-shrink-0">
                      <div className="w-12 h-12 rounded-lg bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-600 dark:text-primary-400">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>
                        </svg>
                      </div>
                    </div>
                    <div>
                      <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">{t.corporateTariffs}</h4>
                      <p className="text-gray-600 dark:text-gray-400">
                        {t.corporateTariffsDesc}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 bg-gradient-to-br from-primary-500/20 to-secondary-500/20 dark:from-primary-900/30 dark:to-secondary-900/30">
        <div className="container-custom">
          <div className="max-w-3xl mx-auto text-center">
            <h2 className="text-3xl md:text-4xl font-bold mb-6 text-gray-900 dark:text-white">
              {t.readyForExam}
            </h2>
            <p className="text-lg text-gray-800 dark:text-gray-200 mb-8">
              {t.startPreparation}
            </p>
            <div className="flex justify-center mt-8">
              <Link to="/registration" className="btn bg-gradient-to-r from-primary-500 to-primary-700 hover:from-primary-600 hover:to-primary-800 text-white px-8 py-3 text-lg rounded-lg font-medium transition-all shadow-md hover:shadow-xl transform hover:-translate-y-0.5 duration-200">
                {t.startTesting}
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section id="faq" className="py-20 bg-gradient-to-br from-white to-gray-50 dark:from-dark-800 dark:to-dark-900/95">
        <div className="container-custom">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4 text-gray-900 dark:text-white">
              {t.faqTitle} <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-primary-500">{language === 'ru' ? 'вопросы' : ''}</span>
            </h2>
            <p className="text-xl text-gray-700 dark:text-gray-300 max-w-3xl mx-auto">
              {language === 'ru' ? 'Ответы на популярные вопросы о нашем сервисе и подготовке к экзаменам' : 
               language === 'kz' ? 'Біздің қызмет және емтихандарға дайындалу туралы жиі қойылатын сұрақтарға жауаптар' : 
               'Answers to popular questions about our service and exam preparation'}
            </p>
          </div>

          <div className="max-w-4xl mx-auto">
            <div className="space-y-6">
              {/* FAQ Item 1 */}
              <div className="card-subtle">
                <h3 className="text-xl font-bold mb-3 text-gray-900 dark:text-white">{t.faqRefSystem}</h3>
                <p className="text-gray-700 dark:text-gray-300">
                  {t.faqRefAnswer}
                </p>
              </div>

              {/* FAQ Item 2 */}
              <div className="card-subtle">
                <h3 className="text-xl font-bold mb-3 text-gray-900 dark:text-white">{t.faqMultiplayer}</h3>
                <p className="text-gray-700 dark:text-gray-300">
                  {t.faqMultiplayerAnswer}
                </p>
              </div>

              {/* FAQ Item 3 */}
              <div className="card-subtle">
                <h3 className="text-xl font-bold mb-3 text-gray-900 dark:text-white">{t.faqGifts}</h3>
                <p className="text-gray-700 dark:text-gray-300">
                  {t.faqGiftsAnswer}
                </p>
              </div>

              {/* FAQ Item 4 */}
              <div className="card-subtle">
                <h3 className="text-xl font-bold mb-3 text-gray-900 dark:text-white">{t.faqUpdates}</h3>
                <p className="text-gray-700 dark:text-gray-300">
                  {t.faqUpdatesAnswer}
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Contact and About Section */}
      <section className="py-16 bg-gradient-to-br from-gray-50 to-white dark:from-dark-900 dark:to-dark-800">
        <div className="container-custom">
          <div className="bg-white/90 dark:bg-dark-800/90 backdrop-blur-sm rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="grid grid-cols-1 lg:grid-cols-5">
              {/* Contact Info */}
              <div className="lg:col-span-2 p-8 bg-gradient-to-br from-primary-500/10 to-secondary-500/10 dark:from-primary-900/20 dark:to-secondary-900/20">
                <h3 className="text-2xl font-bold mb-6 text-gray-900 dark:text-white">
                  {t.ecosystemProduct} <span className="bg-gradient-to-br from-primary-400 to-secondary-500 bg-clip-text text-transparent">Royal One</span>
                </h3>
                <p className="text-gray-800 dark:text-gray-300 mb-6">
                  {t.ecosystemDesc}
                </p>
                <p className="text-gray-800 dark:text-gray-300 mb-6">
                  {t.platformOffers}
                </p>
                <ul className="space-y-3 text-gray-800 dark:text-gray-300 mb-8">
                  <li className="flex items-start">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-500 mr-2 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    {t.accessAllCategories}
                  </li>
                  <li className="flex items-start">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-500 mr-2 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    {t.multilingualInterface}
                  </li>
                  <li className="flex items-start">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-500 mr-2 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    {t.regularlyUpdated}
                  </li>
                </ul>
                <a href="https://wa.me/message/DXDO6BJNOMFNF1" className="inline-flex items-center justify-center bg-green-500 hover:bg-green-600 text-white px-6 py-3 rounded-lg transition-all transform hover:-translate-y-1 hover:shadow-lg active:translate-y-0 text-sm md:text-base">
                  <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.372-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.095 3.2 5.076 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.57-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                  </svg>
                  {t.contactViaWhatsapp}
                </a>
              </div>

              {/* About Driving School */}
              <div className="lg:col-span-3 p-8">
                <h3 className="text-2xl font-bold mb-6 text-gray-900 dark:text-white">
                  {t.drivingSchoolTitle} <span className="bg-gradient-to-br from-primary-400 to-secondary-500 bg-clip-text text-transparent">Royal Driving</span>
                </h3>
                <p className="text-gray-800 dark:text-gray-300 mb-6">
                  {t.drivingSchoolDesc5years}
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                  <div className="flex items-start">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-500 mr-3 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    <div>
                      <h4 className="font-semibold text-gray-900 dark:text-white">{t.experiencedInstructors}</h4>
                      <p className="text-sm text-gray-700 dark:text-gray-400">{t.instructorsDesc}</p>
                  </div>
                  </div>
                  <div className="flex items-start">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-500 mr-3 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>
                    </svg>
                    <div>
                      <h4 className="font-semibold text-gray-900 dark:text-white">{t.comfortableClassrooms}</h4>
                      <p className="text-sm text-gray-700 dark:text-gray-400">{t.classroomsDesc}</p>
                  </div>
                  </div>
                  <div className="flex items-start">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-500 mr-3 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                    </svg>
                    <div>
                      <h4 className="font-semibold text-gray-900 dark:text-white">{t.ecosystem}</h4>
                      <p className="text-sm text-gray-700 dark:text-gray-400">{t.ecosystemServiceDesc}</p>
                    </div>
                  </div>
                  <div className="flex items-start">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-500 mr-3 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path>
                    </svg>
                    <div>
                      <h4 className="font-semibold text-gray-900 dark:text-white">{t.specialZoneSupport}</h4>
                      <p className="text-sm text-gray-700 dark:text-gray-400">{t.supportExamsDesc}</p>
                    </div>
                  </div>
                </div>
                <div className="bg-gray-50 dark:bg-dark-700/50 p-4 rounded-lg border border-gray-200 dark:border-gray-700 mb-4">
                  <h4 className="font-semibold text-gray-900 dark:text-white mb-2 flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-500 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    {t.notAbandoningYou}
                  </h4>
                  <p className="text-sm text-gray-700 dark:text-gray-400">
                    {t.communityDesc}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default HomePage; 