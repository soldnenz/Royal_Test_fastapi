import { Link } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';
import { translations } from '../translations/translations';

const Footer = () => {
  const currentYear = new Date().getFullYear();
  const { language } = useLanguage();
  const t = translations[language];
  
  return (
    <footer className="bg-white dark:bg-dark-800 border-t border-gray-200 dark:border-gray-700 pt-12 pb-6 shadow-inner">
      <div className="container-custom">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {/* Brand Section */}
          <div className="col-span-1">
            <h3 className="text-xl font-bold mb-4">
              <span className="bg-gradient-to-r from-primary-500 to-primary-600 bg-clip-text text-transparent drop-shadow-sm">
                Royal<span className="text-gray-900 dark:text-white">One</span>
              </span>
            </h3>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              {t.footerDesc}
            </p>
          </div>

          {/* Quick Links */}
          <div className="col-span-1">
            <h4 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">{t.navigation}</h4>
            <ul className="space-y-2">
              <li>
                <a href="#categories" className="text-gray-700 dark:text-gray-300 hover:text-primary-500 dark:hover:text-primary-400">
                  {t.testCategories}
                </a>
              </li>
              <li>
                <a href="#pricing" className="text-gray-700 dark:text-gray-300 hover:text-primary-500 dark:hover:text-primary-400">
                  {t.tariffs}
                </a>
              </li>
              <li>
                <a href="#faq" className="text-gray-700 dark:text-gray-300 hover:text-primary-500 dark:hover:text-primary-400">
                  {t.frequentQuestions}
                </a>
              </li>
            </ul>
          </div>

          {/* Features Section */}
          <div className="col-span-1">
            <h4 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">{t.specialFeatures}</h4>
            <ul className="space-y-2">
              <li className="text-gray-700 dark:text-gray-300">
                {t.currentDb}
              </li>
              <li className="text-gray-700 dark:text-gray-300">
                {t.multiplayerCompetitions}
              </li>
              <li className="text-gray-700 dark:text-gray-300">
                {t.detailedAnswerExplanations}
              </li>
              <li className="text-gray-700 dark:text-gray-300">
                {t.gamificationAchievements} <span className="text-xs text-primary-500">{t.comingSoon}</span>
              </li>
              <li className="text-gray-700 dark:text-gray-300">
                {t.statisticsProgress}
              </li>
              <li className="text-gray-700 dark:text-gray-300">
                {t.referralSystem}
              </li>
            </ul>
          </div>

          {/* Contact Section */}
          <div className="col-span-1">
            <h4 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">{t.contactUs}</h4>
            <div className="space-y-3">
              <div className="flex items-center space-x-3">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
                </svg>
                <span className="text-gray-700 dark:text-gray-300">{t.telegram}</span>
              </div>
              <div className="flex items-center space-x-3">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-2-2 2 2 0 00-2 2v7h-4v-7a6 6 0 016-6zM2 9h4v12H2z" />
                </svg>
                <a 
                  href="https://www.instagram.com/royal_test_kz" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-gray-700 dark:text-gray-300 hover:text-primary-500 dark:hover:text-primary-400"
                >
                  {t.instagram}
                </a>
              </div>
              <div className="flex items-center space-x-3">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                </svg>
                <a 
                  href="https://wa.me/message/DXDO6BJNOMFNF1" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-gray-700 dark:text-gray-300 hover:text-primary-500 dark:hover:text-primary-400"
                >
                  {t.whatsapp}
                </a>
              </div>
            </div>
            
            <div className="mt-6 bg-gray-50 dark:bg-dark-700/50 p-4 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
              <h5 className="font-medium text-gray-900 dark:text-white mb-2">{t.drivingSchool}</h5>
              <p className="text-sm text-gray-700 dark:text-gray-300">
                {t.drivingSchoolDesc}
              </p>
            </div>
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-gray-200 dark:border-gray-700 my-8"></div>

        {/* Copyright */}
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="text-gray-700 dark:text-gray-300 text-sm">
            <p>© {currentYear} Royal Test. {t.allRightsReserved}</p>
          </div>
          <div className="flex space-x-4">
            <a href="#" className="text-sm text-gray-600 dark:text-gray-400 hover:text-primary-500 dark:hover:text-primary-400">
              {t.termsOfUse}
            </a>
            <a href="#" className="text-sm text-gray-600 dark:text-gray-400 hover:text-primary-500 dark:hover:text-primary-400">
              {t.privacyPolicy}
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer; 