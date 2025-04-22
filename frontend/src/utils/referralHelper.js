/**
 * Extracts referral code from URL and stores it in localStorage
 * Used for when someone visits the site with a referral link
 * @returns {string|null} The referral code extracted from URL or null if not present
 */
export const handleReferralFromUrl = () => {
  // Check if there's a referral code in the URL (supports both ?referralCode= and ?ref= formats)
  const params = new URLSearchParams(window.location.search);
  let refCode = params.get('referralCode') || params.get('ref');
  
  // If we found a referral code in the URL
  if (refCode) {
    // Store it in localStorage for later use in registration
    localStorage.setItem('referralCode', refCode);
    return refCode;
  }
  
  return null;
};

/**
 * Gets the stored referral code from localStorage if available
 * @returns {string|null} The stored referral code or null if not present
 */
export const getStoredReferralCode = () => {
  return localStorage.getItem('referralCode');
};

/**
 * Clears the referral code from localStorage
 * Used after successful registration
 */
export const clearReferralCode = () => {
  localStorage.removeItem('referralCode');
}; 