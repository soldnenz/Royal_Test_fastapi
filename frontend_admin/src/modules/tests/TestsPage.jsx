import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate, useParams } from 'react-router-dom';
import TestsList from './TestsList';
import TestCreator from './TestCreator';
import TestEditor from './TestEditor';
import './Tests.css';

const TestsPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { uid } = useParams(); // Get UID from URL params if available
  
  // If we have a UID from URL params, use that, otherwise look in search params
  const testUid = uid || searchParams.get('uid');
  
  // If we came directly to an edit URL, set activeTab to 'edit'
  const defaultTab = uid ? 'edit' : 'list';
  const activeTab = searchParams.get('tab') || defaultTab;

  useEffect(() => {
    // If we have a UID from URL params but no tab in search params, update URL
    if (uid && !searchParams.get('tab')) {
      const newParams = new URLSearchParams(searchParams);
      newParams.set('tab', 'edit');
      newParams.set('uid', uid);
      navigate({ search: newParams.toString() }, { replace: true });
    }
  }, [uid, searchParams, navigate]);

  const handleTabChange = (tab, params = {}) => {
    const newParams = new URLSearchParams();
    newParams.set('tab', tab);
    
    // Add any additional params
    Object.entries(params).forEach(([key, value]) => {
      if (value) newParams.set(key, value);
    });
    
    navigate({ search: newParams.toString() });
  };

  return (
    <div className="tests-container">
      <div className="page-header">
        <div className="tabs-container">
          <button 
            className={`tab-button ${activeTab === 'list' ? 'active' : ''}`}
            onClick={() => handleTabChange('list')}
          >
            Список вопросов
          </button>
          <button 
            className={`tab-button ${activeTab === 'create' ? 'active' : ''}`}
            onClick={() => handleTabChange('create')}
          >
            Создать вопрос
          </button>
          {activeTab === 'edit' && (
            <button 
              className="tab-button active"
            >
              Редактирование вопроса
            </button>
          )}
        </div>
      </div>

      <div className="tab-content">
        {activeTab === 'list' && <TestsList onEditQuestion={(uid) => handleTabChange('edit', { uid })} />}
        {activeTab === 'create' && <TestCreator onCreated={() => handleTabChange('list')} />}
        {activeTab === 'edit' && testUid && <TestEditor uid={testUid} onClose={() => handleTabChange('list')} />}
      </div>
    </div>
  );
};

export default TestsPage; 