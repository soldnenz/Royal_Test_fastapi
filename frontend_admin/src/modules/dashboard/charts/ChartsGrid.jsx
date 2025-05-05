import React, { useState } from 'react';
import './ChartsGrid.css';

// Компонент карточки графика с фейковыми данными
const ChartCard = ({ title, children, chartType = 'bar' }) => {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className={`chart-card ${expanded ? 'expanded' : ''}`}>
      <div className="chart-header">
        <h3 className="chart-title">{title}</h3>
        <div className="chart-actions">
          <button className="chart-action-btn" aria-label="Обновить">
            <i className="bx bx-refresh"></i>
          </button>
          <button 
            className="chart-action-btn" 
            aria-label={expanded ? "Свернуть" : "Развернуть"}
            onClick={() => setExpanded(!expanded)}
          >
            <i className={`bx ${expanded ? 'bx-collapse' : 'bx-expand'}`}></i>
          </button>
        </div>
      </div>
      <div className="chart-container">
        {children || (
          <div className="chart-placeholder">
            <div className={`chart-mockup chart-mockup-${chartType}`}>
              {chartType === 'bar' && (
                <>
                  <div className="mockup-bar" style={{height: '65%'}}></div>
                  <div className="mockup-bar" style={{height: '85%'}}></div>
                  <div className="mockup-bar" style={{height: '40%'}}></div>
                  <div className="mockup-bar" style={{height: '70%'}}></div>
                  <div className="mockup-bar" style={{height: '90%'}}></div>
                  <div className="mockup-bar" style={{height: '50%'}}></div>
                </>
              )}
              {chartType === 'line' && (
                <div className="mockup-line">
                  <svg viewBox="0 0 100 50" preserveAspectRatio="none">
                    <path d="M0,40 L10,38 L20,30 L30,25 L40,28 L50,20 L60,15 L70,18 L80,10 L90,12 L100,5" />
                  </svg>
                </div>
              )}
              {chartType === 'pie' && (
                <div className="mockup-pie">
                  <div className="pie-segment" style={{transform: 'rotate(0deg)', background: 'var(--accent)'}}></div>
                  <div className="pie-segment" style={{transform: 'rotate(120deg)', background: '#3182ce'}}></div>
                  <div className="pie-segment" style={{transform: 'rotate(220deg)', background: '#38a169'}}></div>
                </div>
              )}
              {chartType === 'map' && (
                <div className="mockup-map">
                  <div className="map-region" style={{top: '20%', left: '15%', width: '20%', height: '15%'}}></div>
                  <div className="map-region" style={{top: '40%', left: '35%', width: '35%', height: '25%'}}></div>
                  <div className="map-region" style={{top: '25%', left: '70%', width: '15%', height: '40%'}}></div>
                  <div className="map-dot" style={{top: '25%', left: '20%'}}></div>
                  <div className="map-dot" style={{top: '45%', left: '50%'}}></div>
                  <div className="map-dot" style={{top: '35%', left: '75%'}}></div>
                  <div className="map-dot" style={{top: '60%', left: '30%'}}></div>
                  <div className="map-dot" style={{top: '70%', left: '60%'}}></div>
                </div>
              )}
            </div>
            <div className="chart-labels">
              {chartType === 'bar' && (
                <>
                  <div className="chart-axis-x">
                    <span>Янв</span>
                    <span>Фев</span>
                    <span>Мар</span>
                    <span>Апр</span>
                    <span>Май</span>
                    <span>Июн</span>
                  </div>
                  <div className="chart-axis-y">
                    <span>0</span>
                    <span>25</span>
                    <span>50</span>
                    <span>75</span>
                    <span>100</span>
                  </div>
                </>
              )}
              {chartType === 'line' && (
                <>
                  <div className="chart-axis-x">
                    <span>Янв</span>
                    <span>Фев</span>
                    <span>Мар</span>
                    <span>Апр</span>
                    <span>Май</span>
                    <span>Июн</span>
                  </div>
                </>
              )}
              {chartType === 'pie' && (
                <div className="chart-legend">
                  <div className="legend-item"><span style={{background: 'var(--accent)'}}></span>Базовые (35%)</div>
                  <div className="legend-item"><span style={{background: '#3182ce'}}></span>Продвинутые (40%)</div>
                  <div className="legend-item"><span style={{background: '#38a169'}}></span>Премиум (25%)</div>
                </div>
              )}
              {chartType === 'map' && (
                <div className="chart-legend">
                  <div className="legend-item"><span className="dot-legend"></span>Активные пользователи</div>
                  <div className="legend-item"><span className="region-legend"></span>Регионы с высокой активностью</div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Компонент сетки графиков
const ChartsGrid = () => {
  return (
    <section className="charts-section">
      <div className="stats-header">
        <h2 className="section-heading">Аналитика и графики</h2>
        <div className="chart-actions-global">
          <button className="chart-period-btn active">День</button>
          <button className="chart-period-btn">Неделя</button>
          <button className="chart-period-btn">Месяц</button>
          <button className="chart-period-btn">Год</button>
        </div>
      </div>
      <div className="charts-grid">
        <ChartCard title="Активность пользователей" chartType="line" />
        <ChartCard title="Типы тестов" chartType="pie" />
        <ChartCard title="Доходы по месяцам" chartType="bar" />
        <ChartCard title="География пользователей" chartType="map" />
      </div>
    </section>
  );
};

export default ChartsGrid; 