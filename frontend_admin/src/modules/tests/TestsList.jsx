import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Table, Input, Select, Space, Progress, message, Tag, Modal, Card, Spin, Empty, Row, Col, Divider, Radio } from 'antd';
import { SearchOutlined, FilterOutlined, EyeOutlined, DeleteOutlined, ExclamationCircleOutlined, PlayCircleOutlined, GlobalOutlined, CloseCircleOutlined } from '@ant-design/icons';
import axios from 'axios';
import { PDD_SECTIONS, PDD_CATEGORIES } from '../../shared/config';
import './Tests.css';

const { Search } = Input;
const { Option } = Select;
const { confirm } = Modal;

const TestsList = () => {
  const [tests, setTests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [selectedSections, setSelectedSections] = useState([]);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [mediaFilter, setMediaFilter] = useState('all');
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [initialLoading, setInitialLoading] = useState(true);
  const [modalInfo, setModalInfo] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [language, setLanguage] = useState('ru');
  const abortControllerRef = useRef(null);
  const navigate = useNavigate();

  const fetchTests = async () => {
    setLoading(true);
    setInitialLoading(true);
    setLoadingProgress(0);
    try {
      const response = await axios.get('/api/tests/all', {
        onDownloadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            setLoadingProgress(percentCompleted);
          }
        }
      });
      setTests(response.data.data);
      
      setLoadingProgress(100);
      
      setTimeout(() => {
        setInitialLoading(false);
      }, 500);
    } catch (error) {
      message.error('Ошибка при загрузке тестов');
      console.error('Error fetching tests:', error);
      setInitialLoading(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTests();
    
    const isDarkMode = document.body.classList.contains('dark-theme');
    if (isDarkMode) {
      document.querySelector('.tests-list-container')?.classList.add('dark-theme-support');
      document.querySelectorAll('.ant-table, .ant-card').forEach(element => {
        element.classList.add('dark-theme-support');
      });
    }
    
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          const isDark = document.body.classList.contains('dark-theme');
          if (isDark) {
            document.querySelector('.tests-list-container')?.classList.add('dark-theme-support');
            document.querySelectorAll('.ant-table, .ant-card').forEach(element => {
              element.classList.add('dark-theme-support');
            });
          } else {
            document.querySelector('.tests-list-container')?.classList.remove('dark-theme-support');
            document.querySelectorAll('.ant-table, .ant-card').forEach(element => {
              element.classList.remove('dark-theme-support');
            });
          }
        }
      });
    });
    
    observer.observe(document.body, { attributes: true });
    
    return () => {
      observer.disconnect();
    };
  }, []);

  const handleSearch = (value) => {
    setSearchText(value);
  };

  const handleSectionChange = (value) => {
    setSelectedSections(value);
  };

  const handleCategoryChange = (value) => {
    setSelectedCategories(value);
  };

  const handleMediaFilterChange = (value) => {
    setMediaFilter(value);
  };

  const handleLanguageChange = (e) => {
    setLanguage(e.target.value);
  };

  const sectionMap = Object.fromEntries(PDD_SECTIONS.map(s => [s.uid, s.title]));

  const filteredTests = tests.filter(test => {
    const matchesSearch = searchText === '' || 
      test.question_text[language]?.toLowerCase().includes(searchText.toLowerCase());
    
    const matchesSection = selectedSections.length === 0 ||
      test.pdd_section_uids.some(section => selectedSections.includes(section));
    
    const matchesCategory = selectedCategories.length === 0 ||
      test.categories.some(cat => selectedCategories.includes(cat));
    
    const matchesMedia = 
      mediaFilter === 'all' ||
      (mediaFilter === 'with' && test.has_media) ||
      (mediaFilter === 'without' && !test.has_media) ||
      (mediaFilter === 'main-video' && test.media_filename && test.media_filename.endsWith('.mp4')) ||
      (mediaFilter === 'additional-video' && test.after_answer_media_filename && test.after_answer_media_filename.endsWith('.mp4'));
    
    return matchesSearch && matchesSection && matchesCategory && matchesMedia;
  });

  const showDeleteConfirm = (uid) => {
    console.log('showDeleteConfirm called with UID:', uid);
    try {
      const result = window.confirm('Вы уверены, что хотите удалить этот вопрос? Это действие невозможно отменить.');
      if (result) {
        console.log('Delete confirmed for UID:', uid);
        deleteTest(uid);
      } else {
        console.log('Delete cancelled for UID:', uid);
      }
    } catch (error) {
      console.error('Error showing confirmation:', error);
    }
  };

  const deleteTest = async (uid) => {
    try {
      console.log('deleteTest function called with UID:', uid);
      console.log('Making DELETE request to /api/tests/');
      
      const requestData = { question_id: uid };
      console.log('Request data:', requestData);
      
      const response = await axios.delete(`/api/tests/`, {
        data: requestData,
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      console.log('Delete response received:', response);
      console.log('Response status:', response.status);
      console.log('Response data:', response.data);
      
      if (response.status === 200) {
        console.log('Deletion successful, showing success message');
        message.success('Вопрос успешно удален');
        console.log('Refreshing tests list');
        fetchTests(); // Обновляем список
      } else {
        console.error('Unexpected status:', response.status);
        message.error('Ошибка при удалении вопроса');
      }
    } catch (error) {
      console.error('Error in deleteTest function:', error);
      console.error('Error message:', error.message);
      console.error('Error response:', error.response);
      console.error('Error response data:', error.response?.data);
      console.error('Error response status:', error.response?.status);
      message.error(error.response?.data?.detail || 'Ошибка при удалении вопроса');
    }
  };

  const handleViewDetails = async (record) => {
    setModalInfo(record);
    setDetailsLoading(true);
    
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();
    
    try {
      console.log('Loading details for test:', record.uid);
      
      const response = await axios.get(`/api/tests/by_uid/${record.uid}`, {
        onDownloadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            setLoadingProgress(percentCompleted);
          }
        },
        signal: abortControllerRef.current.signal
      });
      
      const responseData = response.data.data;
      console.log('Test details loaded:', responseData);
      console.log('After answer media info:', {
        after_answer_media_file_id: responseData.after_answer_media_file_id,
        after_answer_media_id: responseData.after_answer_media_id,
        has_after_answer_media: responseData.has_after_answer_media,
        has_after_media: responseData.has_after_media,
        after_answer_media_filename: responseData.after_answer_media_filename
      });
      setModalInfo(responseData);
      
    } catch (error) {
      if (!axios.isCancel(error)) {
        console.error('Error fetching test details:', error);
        message.error('Ошибка при загрузке информации о тесте');
      }
    } finally {
      setDetailsLoading(false);
    }
  };

  const cancelRequest = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setDetailsLoading(false);
      message.info('Запрос отменен');
    }
  };

  // Функция для получения URL медиафайла
  const getMediaUrl = (mediaId) => {
    if (!mediaId) return null;
    return `/api/tests/media/${mediaId}`;
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'uid',
      key: 'uid',
      width: 100,
      className: 'id-column',
    },
    {
      title: 'Вопрос',
      dataIndex: 'question_text',
      key: 'question_text',
      render: (text) => (
        <div className="question-text-cell">{text[language]}</div>
      ),
    },
    {
      title: 'Разделы ПДД',
      dataIndex: 'pdd_section_uids',
      key: 'pdd_section_uids',
      width: 200,
      render: (sections) => (
        <div className="table-tags-container">
          {sections.map(section => (
            <Tag key={section} className="pdd-section-tag" style={{ display: 'inline-block', margin: '2px' }}>
              {sectionMap[section] || section}
            </Tag>
          ))}
        </div>
      ),
    },
    {
      title: 'Категории',
      dataIndex: 'categories',
      key: 'categories',
      width: 150,
      render: (cats) => (
        <div className="table-tags-container">
          {cats.map(cat => (
            <Tag key={cat} className="category-tag" style={{ display: 'inline-block', margin: '2px' }}>
              {cat}
            </Tag>
          ))}
        </div>
      ),
    },
    {
      title: 'Медиа',
      dataIndex: 'has_media',
      key: 'has_media',
      width: 90,
      render: (hasMedia) => hasMedia ? 
        <Tag color="blue" className="media-tag">Есть</Tag> : 
        <Tag color="default" className="media-tag">Нет</Tag>,
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <div className="action-buttons-column">
          <Button 
            icon={<EyeOutlined />} 
            onClick={() => handleViewDetails(record)}
            className="action-btn info"
            block
          >
            Подробнее
          </Button>
          <Button 
            icon={<DeleteOutlined />} 
            danger
            onClick={(e) => {
              console.log('=== DELETE BUTTON CLICKED ===');
              console.log('Event:', e);
              console.log('Record:', record);
              console.log('Record UID:', record?.uid);
              
              e.preventDefault();
              e.stopPropagation();
              
              if (!record || !record.uid) {
                console.error('No record or UID found');
                return;
              }
              
              try {
                console.log('Calling showDeleteConfirm with UID:', record.uid);
                showDeleteConfirm(record.uid);
              } catch (error) {
                console.error('Error in onClick handler:', error);
              }
            }}
            className="action-btn delete"
            style={{ pointerEvents: 'auto', cursor: 'pointer' }}
            block
          >
            Удалить
          </Button>
          <Button 
            type="primary" 
            onClick={() => navigate(`/tests/edit/${record.uid}`)}
            className="action-btn edit"
            block
          >
            Редактировать
          </Button>
        </div>
      ),
    },
  ];

  const renderModal = () => {
    if (!modalInfo) return null;

    const isDark = document.body.classList.contains('dark-theme');
    const hasMainMedia = !!modalInfo.media_file_id;
    const hasAfterAnswerMedia = !!(modalInfo.after_answer_media_file_id || modalInfo.after_answer_media_id || modalInfo.has_after_answer_media || modalInfo.has_after_media);
    
    // Получаем URL для медиафайлов
    const mainMediaUrl = getMediaUrl(modalInfo.media_file_id);
    const afterAnswerMediaUrl = getMediaUrl(modalInfo.after_answer_media_file_id || modalInfo.after_answer_media_id);
    
    // Определяем тип контента на основе расширения файла
    const getContentType = (filename) => {
      if (!filename) return 'image/jpeg';
      const ext = filename.toLowerCase();
      if (ext.endsWith('.mp4') || ext.endsWith('.webm') || ext.endsWith('.mov')) {
        return 'video/mp4';
      } else if (ext.endsWith('.png')) {
        return 'image/png';
      } else if (ext.endsWith('.jpg') || ext.endsWith('.jpeg')) {
        return 'image/jpeg';
      } else if (ext.endsWith('.gif')) {
        return 'image/gif';
      } else if (ext.endsWith('.webp')) {
        return 'image/webp';
      }
      return 'image/jpeg';
    };
    
    const mainMediaType = getContentType(modalInfo.media_filename);
    const afterAnswerMediaType = getContentType(modalInfo.after_answer_media_filename);
    
    return (
      <Modal
        open={!!modalInfo}
        title={
          <div>
            <span>Вопрос #{modalInfo.uid}</span>
            <div style={{ fontSize: '12px', marginTop: '4px' }}>
              {hasMainMedia && <Tag color="blue">Основное медиа</Tag>}
              {hasAfterAnswerMedia && <Tag color="green">Дополнительное медиа</Tag>}
            </div>
          </div>
        }
        onCancel={() => {
          cancelRequest();
          setModalInfo(null);
        }}
        footer={[
          detailsLoading ? (
            <Button key="cancel" 
              danger
              icon={<CloseCircleOutlined />}
              onClick={cancelRequest}
            >
              Отменить загрузку
            </Button>
          ) : (
            <Button key="edit" 
              type="primary" 
              onClick={() => {
                setModalInfo(null);
                navigate(`/tests/edit/${modalInfo.uid}`);
              }}
            >
              Редактировать
            </Button>
          ),
          <Button key="close" onClick={() => {
            cancelRequest();
            setModalInfo(null);
          }}>
            Закрыть
          </Button>
        ]}
        width={800}
        className={`detail-modal ${isDark ? 'dark-theme-support' : ''} ${detailsLoading ? 'loading-modal' : ''}`}
        style={isDark ? { background: 'var(--bg-dark, #1f1f1f)' } : {}}
        maskClosable={!detailsLoading}
        closable={!detailsLoading}
      >
        {detailsLoading && (
          <div className="modal-loading-overlay">
            <div className="loading-content">
              <Spin size="large" />
              <Progress 
                percent={loadingProgress} 
                status="active" 
                strokeColor={{
                  '0%': '#1890ff',
                  '100%': '#52c41a',
                }}
                style={{ marginTop: 16, width: '80%', maxWidth: 400 }}
              />
              <div className="loading-text">Загрузка данных теста...</div>
              <Button 
                type="primary" 
                danger 
                icon={<CloseCircleOutlined />} 
                onClick={cancelRequest}
                style={{ marginTop: 16 }}
              >
                Отменить загрузку
              </Button>
            </div>
          </div>
        )}
        
        <div className="test-detail-content" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>
          <div className="language-selector-container">
            <Radio.Group value={language} onChange={handleLanguageChange} buttonStyle="solid" className="language-selector">
              <Radio.Button value="ru">RU</Radio.Button>
              <Radio.Button value="kz">KZ</Radio.Button>
              <Radio.Button value="en">EN</Radio.Button>
            </Radio.Group>
          </div>
          
          <Row gutter={[24, 24]}>
            <Col xs={24} md={modalInfo.has_media ? 12 : 24}>
              <Card 
                title="Вопрос" 
                className={`detail-card question-card ${isDark ? 'dark-theme-support' : ''}`}
                style={isDark ? { 
                  background: 'var(--bg-dark-accent, #2a2a2a)',
                  color: 'var(--text-light, #fff)',
                  border: '1px solid var(--border-dark, #333)'
                } : {}}
                headStyle={isDark ? { color: 'var(--text-light, #fff)' } : {}}
              >
                <div 
                  className="detail-text"
                  style={isDark ? { color: 'var(--text-light, #fff)' } : {}}
                >
                  {modalInfo.question_text[language]}
                </div>
                
                <Divider />
                
                <div className="tags-section">
                  <div className="tag-group">
                    <div 
                      className="tag-title"
                      style={isDark ? { color: 'var(--text-light, #fff)' } : {}}
                    >
                      Разделы ПДД:
                    </div>
                    <div className="tag-list">
                      {modalInfo.pdd_section_uids.map(section => (
                        <Tag 
                          key={section} 
                          className="pdd-section-tag"
                          style={isDark ? { 
                            background: 'var(--bg-dark-accent, #2a2a2a)',
                            color: 'var(--text-light, #fff)',
                            borderColor: 'var(--border-dark, #555)'
                          } : {}}
                        >
                          {sectionMap[section] || section}
                        </Tag>
                      ))}
                    </div>
                  </div>
                  
                  <div className="tag-group">
                    <div 
                      className="tag-title"
                      style={isDark ? { color: 'var(--text-light, #fff)' } : {}}
                    >
                      Категории:
                    </div>
                    <div className="tag-list">
                      {modalInfo.categories.map(cat => (
                        <Tag 
                          key={cat} 
                          className="category-tag"
                          style={isDark ? { 
                            background: 'var(--bg-dark-accent, #2a2a2a)',
                            color: 'var(--text-light, #fff)',
                            borderColor: 'var(--border-dark, #555)'
                          } : {}}
                        >
                          {cat}
                        </Tag>
                      ))}
                    </div>
                  </div>
                </div>
              </Card>
            </Col>
            
            {hasMainMedia && (
              <Col xs={24} md={hasAfterAnswerMedia ? 12 : 24}>
                <Card 
                  title={
                    <div>
                      Основное медиа
                      <span style={{ fontSize: '12px', marginLeft: '8px' }}>
                        {modalInfo.media_filename && `(${modalInfo.media_filename})`}
                      </span>
                    </div>
                  }
                  className={`detail-card media-card ${isDark ? 'dark-theme-support' : ''}`}
                  style={isDark ? { 
                    background: 'var(--bg-dark-accent, #2a2a2a)',
                    color: 'var(--text-light, #fff)',
                    border: '1px solid var(--border-dark, #333)'
                  } : {}}
                  headStyle={isDark ? { color: 'var(--text-light, #fff)' } : {}}
                >
                  {mainMediaUrl ? (
                    <div className="media-container">
                      {mainMediaType.startsWith('video/') ? (
                        <video controls className="detail-media" crossOrigin="anonymous">
                          <source src={mainMediaUrl} type={mainMediaType} />
                          Ваш браузер не поддерживает видео.
                        </video>
                      ) : (
                        <img src={mainMediaUrl} alt="Медиа" className="detail-media" />
                      )}
                    </div>
                  ) : (
                    <div className="media-placeholder" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>
                      <PlayCircleOutlined style={isDark ? { color: 'var(--text-light, #fff)' } : {}} />
                      <div>Медиафайл не может быть загружен</div>
                      <div style={{ fontSize: '12px', marginTop: '8px' }}>
                        ID: {modalInfo.media_file_id}
                        {modalInfo.media_filename && <br />}
                        {modalInfo.media_filename && `Файл: ${modalInfo.media_filename}`}
                      </div>
                    </div>
                  )}
                </Card>
              </Col>
            )}
            
            {hasAfterAnswerMedia && (
              <Col xs={24} md={hasMainMedia ? 12 : 24}>
                <Card 
                  title={
                    <div>
                      Дополнительное медиа
                      <span style={{ fontSize: '12px', marginLeft: '8px' }}>
                        {modalInfo.after_answer_media_filename && `(${modalInfo.after_answer_media_filename})`}
                      </span>
                    </div>
                  }
                  className={`detail-card media-card ${isDark ? 'dark-theme-support' : ''}`}
                  style={isDark ? { 
                    background: 'var(--bg-dark-accent, #2a2a2a)',
                    color: 'var(--text-light, #fff)',
                    border: '1px solid var(--border-dark, #333)'
                  } : {}}
                  headStyle={isDark ? { color: 'var(--text-light, #fff)' } : {}}
                >
                  {afterAnswerMediaUrl ? (
                    <div className="media-container">
                      {afterAnswerMediaType.startsWith('video/') ? (
                        <video 
                          controls 
                          className="detail-media" 
                          crossOrigin="anonymous"
                          onLoadStart={() => console.log('Video load started')}
                          onLoadedData={() => console.log('Video loaded successfully')}
                          onError={(e) => console.error('Video load error:', e)}
                        >
                          <source src={afterAnswerMediaUrl} type={afterAnswerMediaType} />
                          Ваш браузер не поддерживает видео.
                        </video>
                      ) : (
                        <img 
                          src={afterAnswerMediaUrl} 
                          alt="Доп. медиа" 
                          className="detail-media"
                          onLoad={() => console.log('Image loaded successfully')}
                          onError={(e) => console.error('Image load error:', e)}
                        />
                      )}
                    </div>
                  ) : (
                    <div className="media-placeholder" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>
                      <PlayCircleOutlined style={isDark ? { color: 'var(--text-light, #fff)' } : {}} />
                      <div>Дополнительный медиафайл не может быть загружен</div>
                      <div style={{ fontSize: '12px', marginTop: '8px' }}>
                        ID: {modalInfo.after_answer_media_file_id || modalInfo.after_answer_media_id}
                        {modalInfo.after_answer_media_filename && <br />}
                        {modalInfo.after_answer_media_filename && `Файл: ${modalInfo.after_answer_media_filename}`}
                      </div>
                    </div>
                  )}
                </Card>
              </Col>
            )}
            
            <Col xs={24}>
              <Card 
                title="Варианты ответов" 
                className={`detail-card options-card ${isDark ? 'dark-theme-support' : ''}`}
                style={isDark ? { 
                  background: 'var(--bg-dark-accent, #2a2a2a)',
                  color: 'var(--text-light, #fff)',
                  border: '1px solid var(--border-dark, #333)'
                } : {}}
                headStyle={isDark ? { color: 'var(--text-light, #fff)' } : {}}
              >
                <ul className="options-list">
                  {modalInfo.options.map((opt) => (
                    <li 
                      key={opt.label} 
                      className={opt.label === modalInfo.correct_label ? 'correct-option' : ''}
                      style={isDark ? { color: 'var(--text-light, #fff)' } : {}}
                    >
                      <span className="option-label" style={isDark ? { 
                        background: opt.label === modalInfo.correct_label ? 'var(--success-color)' : 'var(--primary-color)', 
                        color: '#fff' 
                      } : {}}>
                        {opt.label}
                      </span> {opt.text[language]}
                      {opt.label === modalInfo.correct_label && 
                        <span className="correct-mark" style={isDark ? { color: 'var(--success-color)' } : {}}>
                          ✓ Правильный
                        </span>
                      }
                    </li>
                  ))}
                </ul>
              </Card>
            </Col>
            
            {modalInfo.explanation && modalInfo.explanation[language] && (
              <Col xs={24}>
                <Card 
                  title="Пояснение" 
                  className={`detail-card explanation-card ${isDark ? 'dark-theme-support' : ''}`}
                  style={isDark ? { 
                    background: 'var(--bg-dark-accent, #2a2a2a)',
                    color: 'var(--text-light, #fff)',
                    border: '1px solid var(--border-dark, #333)'
                  } : {}}
                  headStyle={isDark ? { color: 'var(--text-light, #fff)' } : {}}
                >
                  <div className="detail-text" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>
                    {modalInfo.explanation[language]}
                  </div>
                </Card>
              </Col>
            )}

            <Col xs={24}>
              <Card 
                title="Дополнительная информация" 
                className={`detail-card info-card ${isDark ? 'dark-theme-support' : ''}`}
                style={isDark ? { 
                  background: 'var(--bg-dark-accent, #2a2a2a)',
                  color: 'var(--text-light, #fff)',
                  border: '1px solid var(--border-dark, #333)'
                } : {}}
                headStyle={isDark ? { color: 'var(--text-light, #fff)' } : {}}
              >
                <div className="info-grid">
                  <div className="info-item" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>
                    <span className="info-label" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>Создан:</span>
                    <span className="info-value" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>
                      {modalInfo.created_at ? new Date(modalInfo.created_at).toLocaleString() : 'Не указано'}
                    </span>
                  </div>
                  {modalInfo.updated_at && (
                    <div className="info-item" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>
                      <span className="info-label" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>Обновлен:</span>
                      <span className="info-value" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>
                        {new Date(modalInfo.updated_at).toLocaleString()}
                      </span>
                    </div>
                  )}
                  {modalInfo.created_by_name && (
                    <div className="info-item" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>
                      <span className="info-label" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>Автор:</span>
                      <span className="info-value" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>
                        {modalInfo.created_by_name}
                      </span>
                    </div>
                  )}
                  {modalInfo.created_by_iin && (
                    <div className="info-item" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>
                      <span className="info-label" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>ИИН автора:</span>
                      <span className="info-value" style={isDark ? { color: 'var(--text-light, #fff)' } : {}}>
                        {modalInfo.created_by_iin}
                      </span>
                    </div>
                  )}
                </div>
              </Card>
            </Col>
          </Row>
        </div>
      </Modal>
    );
  };

  return (
    <div className="tests-list-container">
      {initialLoading ? (
        <div className="loading-container">
          <Spin size="large" />
          <Progress 
            percent={loadingProgress} 
            status="active"
            className="main-progress"
          />
          <div className="loading-text">Загрузка вопросов...</div>
        </div>
      ) : (
        <>
          <div className="tests-filters-container">
            <Space className="tests-filters" wrap>
              <Search
                placeholder="Поиск по вопросу..."
                allowClear
                enterButton={<SearchOutlined />}
                onSearch={handleSearch}
                onChange={(e) => setSearchText(e.target.value)}
                style={{ width: 300, maxWidth: '100%' }}
              />
              <Select
                mode="multiple"
                allowClear
                placeholder="Фильтр по разделам ПДД"
                style={{ minWidth: 220, width: 'auto' }}
                onChange={handleSectionChange}
                suffixIcon={<FilterOutlined />}
                value={selectedSections}
                maxTagCount={2}
              >
                {PDD_SECTIONS.map(section => (
                  <Option key={section.uid} value={section.uid}>{section.title}</Option>
                ))}
              </Select>
              <Select
                mode="multiple"
                allowClear
                placeholder="Фильтр по категориям"
                style={{ minWidth: 150, width: 'auto' }}
                onChange={handleCategoryChange}
                value={selectedCategories}
                maxTagCount={3}
              >
                {PDD_CATEGORIES.map(cat => (
                  <Option key={cat} value={cat}>{cat}</Option>
                ))}
              </Select>
              <Select
                value={mediaFilter}
                onChange={handleMediaFilterChange}
                style={{ minWidth: 170, width: 'auto' }}
              >
                <Option value="all">Все вопросы</Option>
                <Option value="with">С медиа</Option>
                <Option value="without">Без медиа</Option>
                <Option value="main-video">С основным видео</Option>
                <Option value="additional-video">С доп. видео</Option>
              </Select>
              
              <div className="language-selector-wrapper">
                <Radio.Group value={language} onChange={handleLanguageChange} buttonStyle="solid" className="language-selector">
                  <Radio.Button value="ru">RU</Radio.Button>
                  <Radio.Button value="kz">KZ</Radio.Button>
                  <Radio.Button value="en">EN</Radio.Button>
                </Radio.Group>
              </div>
            </Space>
          </div>

          {loading && (
            <Progress 
              percent={loadingProgress} 
              status="active"
              showInfo={false}
              strokeWidth={4}
              className="progress-thin"
            />
          )}

          <Table
            columns={columns}
            dataSource={filteredTests}
            rowKey="uid"
            loading={loading}
            pagination={{
              pageSize: 10,
              showSizeChanger: true,
              pageSizeOptions: ['10', '20', '50', '100'],
              showTotal: (total) => `Всего ${total} вопросов`,
            }}
            scroll={{ x: true }}
            rowClassName={(record) => record.has_media ? 'has-media-row' : ''}
            locale={{
              emptyText: <Empty description="Нет вопросов, соответствующих фильтрам" />
            }}
            className="data-table"
          />

          {renderModal()}
        </>
      )}
    </div>
  );
};

export default TestsList; 