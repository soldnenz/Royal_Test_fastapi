import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useLanguage } from '../../contexts/LanguageContext';
import { translations } from '../../translations/translations';

const PaymentPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { language } = useLanguage();
  const tLang = translations[language];
  
  // Get payment details from location state or set defaults
  const [paymentDetails, setPaymentDetails] = useState({
    subscriptionType: 'economy',
    duration: 1,
    price: 5000,
    date: new Date().toLocaleDateString(),
    orderId: `ORD-${Math.floor(Math.random() * 100000)}`
  });

  useEffect(() => {
    // If payment details were passed via location state, use them
    if (location.state?.paymentDetails) {
      setPaymentDetails(location.state.paymentDetails);
    }
    
    // Scroll to top on mount
    window.scrollTo(0, 0);
  }, [location]);

  // Format price with thousand separators
  const formatMoney = (amount) => {
    return new Intl.NumberFormat('ru-RU').format(amount) + ' ₸';
  };

  // Get subscription name based on type
  const getSubscriptionName = () => {
    const type = paymentDetails.subscriptionType;
    if (!type) return '';
    return tLang[`${type.toLowerCase()}Title`] || type;
  };

  // Get duration text
  const getDurationText = () => {
    const months = paymentDetails.duration || 1;
    return `${months} ${months === 1 ? (tLang.month || 'month') : (tLang.months || 'months')}`;
  };

  // Function to get appropriate payment title based on transaction type
  const getPaymentTitle = () => {
    if (paymentDetails.isGift) {
      return tLang.fromHisAccount || "С его счета";
    } else {
      return tLang.payment || "Payment";
    }
  };

  // Handle return to subscription page
  const handleReturn = () => {
    navigate('/dashboard/subscription');
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 text-gray-900 dark:text-white">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          {getPaymentTitle()}
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          {tLang.orderReview || 'Please review your order details'}
        </p>
      </div>
      
      {/* Payment Receipt/Invoice */}
      <div className="bg-white dark:bg-gray-800 rounded-xl overflow-hidden shadow-lg border border-gray-200 dark:border-gray-700 mb-8">
        {/* Receipt Header */}
        <div className="bg-gradient-to-r from-primary-600 to-primary-400 px-6 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-white text-xl font-bold">Royal Test</h2>
              <p className="text-white text-opacity-90 text-sm">
                {tLang.paymentInvoice || 'Payment Invoice'}
              </p>
            </div>
            <div className="text-white text-right">
              <p className="font-medium">{tLang.orderNumber || 'Order'}: #{paymentDetails.orderId}</p>
              <p className="text-sm text-white text-opacity-90">{paymentDetails.date}</p>
            </div>
          </div>
        </div>
        
        {/* Receipt Body */}
        <div className="px-6 py-6">
          {/* Customer Info (placeholder) */}
          <div className="mb-6 pb-6 border-b border-gray-200 dark:border-gray-700">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              {tLang.customer || 'Customer'}
            </h3>
            <p className="text-gray-700 dark:text-gray-300">
              {paymentDetails.isGift 
                ? paymentDetails.giftOption === 'iin'
                  ? `${tLang.giftForUser || 'Gift for user with IIN'}: ${paymentDetails.giftIIN}`
                  : (tLang.giftAsPromoCode || 'Gift as promo code for anyone')
                : (tLang.customerInfo || 'Your account information')}
            </p>
            {paymentDetails.isGift && (
              <p className="text-gray-700 dark:text-gray-300 mt-2">
                <span className="font-medium">{tLang.paymentSource || 'Payment source'}:</span> {tLang.fromYourAccount || 'From your account'} 
              </p>
            )}
          </div>
          
          {/* Order Details */}
          <div className="mb-6">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
              {tLang.orderDetails || 'Order Details'}
            </h3>
            
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
              {paymentDetails.isTopUp ? (
                <div className="flex justify-between mb-2">
                  <span className="text-gray-700 dark:text-gray-300">
                    {tLang.topUpAmount || 'Top Up Amount'}:
                  </span>
                  <span className="font-medium text-gray-900 dark:text-white">
                    {formatMoney(paymentDetails.price)}
                  </span>
                </div>
              ) : (
                <>
                  <div className="flex justify-between mb-2">
                    <span className="text-gray-700 dark:text-gray-300">
                      {getSubscriptionName()}
                    </span>
                    <span className="font-medium text-gray-900 dark:text-white">
                      {getDurationText()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700 dark:text-gray-300">
                      {tLang.validUntil || 'Valid Until'}:
                    </span>
                    <span className="font-medium text-gray-900 dark:text-white">
                      {new Date(new Date().setMonth(new Date().getMonth() + paymentDetails.duration)).toLocaleDateString()}
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>
          
          {/* Price Breakdown */}
          <div className="mb-8">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
              {tLang.priceBreakdown || 'Price Breakdown'}
            </h3>
            
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
              <div className="flex justify-between mb-2">
                <span className="text-gray-700 dark:text-gray-300">
                  {paymentDetails.isTopUp 
                    ? (tLang.accountTopUp || 'Account Top Up')
                    : `${getSubscriptionName()} - ${getDurationText()}`}
                </span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {formatMoney(paymentDetails.price)}
                </span>
              </div>
              
              {!paymentDetails.isTopUp && paymentDetails.duration > 1 && (
                <div className="flex justify-between mb-2 text-sm text-gray-500 dark:text-gray-400">
                  <span>
                    {paymentDetails.duration === 3 ? (tLang.discount5 || '5% discount applied') : 
                     paymentDetails.duration === 6 ? (tLang.discount10 || '10% discount applied') : ''}
                  </span>
                  <span>
                    {paymentDetails.duration === 3 ? '-5%' : paymentDetails.duration === 6 ? '-10%' : ''}
                  </span>
                </div>
              )}
              
              <div className="h-px bg-gray-200 dark:bg-gray-600 my-3"></div>
              
              <div className="flex justify-between font-bold">
                <span className="text-gray-900 dark:text-white">
                  {tLang.total || 'Total'}:
                </span>
                <span className="text-xl text-primary-600 dark:text-primary-400">
                  {formatMoney(paymentDetails.price)}
                </span>
              </div>
            </div>
          </div>
          
          {/* Payment Notice */}
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 mb-6">
            <div className="flex items-center">
              <svg className="h-6 w-6 text-yellow-500 dark:text-yellow-400 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
              <div>
                <h4 className="font-medium text-yellow-800 dark:text-yellow-300 mb-1">
                  {tLang.paymentNotice || 'Payment Notice'}
                </h4>
                <p className="text-yellow-700 dark:text-yellow-400 text-sm">
                  {tLang.paymentSystemNotice || 'We are currently in the process of connecting our payment system. Please contact us via WhatsApp to complete your payment.'}
                </p>
                <p className="mt-2 text-yellow-700 dark:text-yellow-400 text-sm font-medium">
                  WhatsApp: +7 (777) 123-4567
                </p>
                {paymentDetails.isGift && paymentDetails.giftOption === 'iin' && (
                  <p className="mt-2 text-yellow-700 dark:text-yellow-400 text-sm">
                    {tLang.giftIINConfirmation || 'Please confirm the recipient IIN when contacting us.'}
                  </p>
                )}
              </div>
            </div>
          </div>
          
          {/* QR Code Placeholder */}
          <div className="mb-6 flex flex-col items-center justify-center">
            <div className="w-32 h-32 bg-gray-200 dark:bg-gray-700 rounded-lg mb-2 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 text-gray-400 dark:text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
              </svg>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {tLang.scanToPay || 'Scan to pay via WhatsApp'}
            </p>
          </div>
          
          {/* Bottom Tear Effect */}
          <div className="flex justify-between py-1">
            {[...Array(40)].map((_, i) => (
              <div key={i} className="w-1.5 h-3 bg-gray-200 dark:bg-gray-700 rounded-full"></div>
            ))}
          </div>
        </div>
        
        {/* Receipt Footer */}
        <div className="bg-gray-50 dark:bg-gray-700 px-6 py-4 text-center">
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            {tLang.receiptFooter || 'Thank you for your purchase!'}
          </p>
          <p className="text-gray-500 dark:text-gray-400 text-xs mt-1">
            Royal Test © {new Date().getFullYear()}
          </p>
        </div>
      </div>
      
      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row justify-center space-y-3 sm:space-y-0 sm:space-x-4">
        <button
          onClick={handleReturn}
          className="px-6 py-2.5 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 rounded-lg font-medium transition-colors"
        >
          {tLang.backToSubscriptions || 'Back to Subscriptions'}
        </button>
        
        <a
          href="https://wa.me/77771234567?text=Hello,%20I%20would%20like%20to%20complete%20my%20payment%20for%20Royal%20Test%20subscription.%20Order%20ID:%20" 
          target="_blank"
          rel="noopener noreferrer"
          className="px-6 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="currentColor" viewBox="0 0 24 24">
            <path d="M.057 24l1.687-6.163c-1.041-1.804-1.588-3.849-1.587-5.946.003-6.556 5.338-11.891 11.893-11.891 3.181.001 6.167 1.24 8.413 3.488 2.245 2.248 3.481 5.236 3.48 8.414-.003 6.557-5.338 11.892-11.893 11.892-1.99-.001-3.951-.5-5.688-1.448l-6.305 1.654zm6.597-3.807c1.676.995 3.276 1.591 5.392 1.592 5.448 0 9.886-4.434 9.889-9.885.002-5.462-4.415-9.89-9.881-9.892-5.452 0-9.887 4.434-9.889 9.884-.001 2.225.651 3.891 1.746 5.634l-.999 3.648 3.742-.981zm11.387-5.464c-.074-.124-.272-.198-.57-.347-.297-.149-1.758-.868-2.031-.967-.272-.099-.47-.149-.669.149-.198.297-.768.967-.941 1.165-.173.198-.347.223-.644.074-.297-.149-1.255-.462-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.297-.347.446-.521.151-.172.2-.296.3-.495.099-.198.05-.372-.025-.521-.075-.148-.669-1.611-.916-2.206-.242-.579-.487-.501-.669-.51l-.57-.01c-.198 0-.52.074-.792.372s-1.04 1.016-1.04 2.479 1.065 2.876 1.213 3.074c.149.198 2.095 3.2 5.076 4.487.709.306 1.263.489 1.694.626.712.226 1.36.194 1.872.118.571-.085 1.758-.719 2.006-1.413.248-.695.248-1.29.173-1.414z"/>
          </svg>
          {tLang.contactViaWhatsApp || 'Contact via WhatsApp'}
        </a>
      </div>
    </div>
  );
};

export default PaymentPage; 