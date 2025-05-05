import React, { useState, useEffect } from 'react';
import UsersList from './components/UsersList';
import UserDetailsModal from './components/UserDetailsModal';
import BalanceModal from './components/BalanceModal';
import SubscriptionModal from './components/SubscriptionModal';
import EditSubscriptionModal from './components/EditSubscriptionModal';
import UserBanModal from './components/UserBanModal';
import { useToast } from '../../shared/ToastContext';
import './UsersPage.css';

const API_BASE_URL = '/api';

const UsersPage = () => {
  const [users, setUsers] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Modal states
  const [selectedUser, setSelectedUser] = useState(null);
  const [showUserDetailsModal, setShowUserDetailsModal] = useState(false);
  const [showBalanceModal, setShowBalanceModal] = useState(false);
  const [showSubscriptionModal, setShowSubscriptionModal] = useState(false);
  const [showEditSubscriptionModal, setShowEditSubscriptionModal] = useState(false);
  const [showUserBanModal, setShowUserBanModal] = useState(false);
  
  const { showToast } = useToast();

  // Handle search
  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      showToast('Введите поисковый запрос', 'error');
      return;
    }

    setIsSearching(true);
    try {
      showToast('Поиск пользователей...', 'info');
      
      const response = await fetch(`${API_BASE_URL}/users/admin/search_users?query=${encodeURIComponent(searchQuery)}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        credentials: 'include'
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        const errorMessage = errorData && errorData.detail && errorData.detail.message 
          ? errorData.detail.message 
          : 'Ошибка поиска';
        throw new Error(errorMessage);
      }
      
      const data = await response.json();
      
      if ((data.status === 'success' || data.status === 'ok') && Array.isArray(data.data)) {
        setUsers(data.data);
        showToast(`Найдено пользователей: ${data.data.length}`, 'success');
      } else {
        setUsers([]);
        showToast('Ничего не найдено', 'error');
      }
    } catch (error) {
      console.error('Search error:', error);
      showToast('Ошибка при поиске', 'error');
      setUsers([]);
    } finally {
      setIsSearching(false);
    }
  };

  // Handle key press for search
  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  // Open modal handlers
  const openUserDetails = (user) => {
    setSelectedUser(user);
    setShowUserDetailsModal(true);
  };

  const openBalanceModal = (user) => {
    setSelectedUser(user);
    setShowBalanceModal(true);
  };

  const openSubscriptionModal = (user) => {
    setSelectedUser(user);
    setShowSubscriptionModal(true);
  };

  const openEditSubscriptionModal = (user) => {
    setSelectedUser(user);
    setShowEditSubscriptionModal(true);
  };

  const openUserBanModal = (user) => {
    setSelectedUser(user);
    setShowUserBanModal(true);
  };

  // Refresh user data after modal actions
  const refreshUserData = () => {
    if (searchQuery.trim()) {
      handleSearch();
    }
  };

  return (
    <div className="content-wrapper">
      <div className="card mb-4">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Список пользователей</h5>
          <div className="search-container">
            <input 
              type="text" 
              className="search-input" 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Поиск пользователей..." 
            />
            <button 
              className="btn-action" 
              onClick={handleSearch}
              disabled={isSearching}
            >
              <i className='bx bx-search'></i>
              {isSearching ? 'Поиск...' : 'Поиск'}
            </button>
          </div>
        </div>
        
        <UsersList 
          users={users} 
          onShowDetails={openUserDetails}
          onShowBalance={openBalanceModal}
          onShowSubscription={openSubscriptionModal}
          onShowEditSubscription={openEditSubscriptionModal}
          onShowBan={openUserBanModal}
        />
      </div>

      {/* Modals */}
      {selectedUser && (
        <>
          <UserDetailsModal 
            show={showUserDetailsModal} 
            onClose={() => setShowUserDetailsModal(false)}
            userId={selectedUser.id}
            onRefresh={refreshUserData}
          />
          
          <BalanceModal
            show={showBalanceModal}
            onClose={() => setShowBalanceModal(false)}
            user={selectedUser}
            onRefresh={refreshUserData}
          />
          
          <SubscriptionModal
            show={showSubscriptionModal}
            onClose={() => setShowSubscriptionModal(false)}
            user={selectedUser}
            onRefresh={refreshUserData}
          />
          
          <EditSubscriptionModal
            show={showEditSubscriptionModal}
            onClose={() => setShowEditSubscriptionModal(false)}
            user={selectedUser}
            onRefresh={refreshUserData}
          />
          
          <UserBanModal
            show={showUserBanModal}
            onClose={() => setShowUserBanModal(false)}
            user={selectedUser}
            onRefresh={refreshUserData}
          />
        </>
      )}
    </div>
  );
};

export default UsersPage; 