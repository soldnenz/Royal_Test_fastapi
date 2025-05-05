import React, { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import TestsList from './TestsList';
import TestCreator from './TestCreator';
import TestEditor from './TestEditor';
import './Tests.css';

const TestsPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const activeTab = searchParams.get('tab') || 'list';
  const testUid = searchParams.get('uid');

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
        <h1>Управление тестами</h1>
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