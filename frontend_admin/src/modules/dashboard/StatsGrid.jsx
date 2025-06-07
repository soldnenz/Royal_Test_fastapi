import React, { useState } from 'react';
import StatCard from './StatCard';
import './StatsGrid.css';

const StatsGrid = () => {
  const [period, setPeriod] = useState('month');
  
  // Данные для разных периодов
  const getStatsByPeriod = (periodType) => {
    // Базовые настройки
    const basePeriodText = {
      'today': 'сегодня',
      'yesterday': 'вчера',
      'week': 'за неделю',
      'month': 'за месяц',
      'year': 'за год'
    };
    
    // Данные статистики для разных периодов
    const stats = [
      {
        title: 'Активные пользователи',
        values: {
          today: '254',
          yesterday: '221',
          week: '1,242',
          month: '2,847',
          year: '14,632'
        },
        icon: 'bx bx-user',
        color: 'blue',
        percentChanges: {
          today: 5.2,
          yesterday: -2.1,
          week: 7.5,
          month: 12.8,
          year: 8.2
        }
      },
      {
        title: 'Завершенные тесты',
        values: {
          today: '487',
          yesterday: '412',
          week: '3,254',
          month: '12,495',
          year: '149,753'
        },
        icon: 'bx bx-test-tube',
        color: 'green', 
        percentChanges: {
          today: 3.1,
          yesterday: -1.4,
          week: 5.2,
          month: 8.3,
          year: 14.5
        }
      },
      {
        title: 'Средний балл',
        values: {
          today: '75.2%',
          yesterday: '73.8%',
          week: '74.1%',
          month: '72.5%',
          year: '68.9%'
        },
        icon: 'bx bx-trophy',
        color: 'purple',
        percentChanges: {
          today: 1.8,
          yesterday: 0.5,
          week: 2.1,
          month: 3.2,
          year: -1.4
        }
      },
      {
        title: 'Доход',
        values: {
          today: '₸3,450',
          yesterday: '₸2,980',
          week: '₸19,420',
          month: '₸89,750',
          year: '₸1,248,970'
        },
        icon: 'bx bx-money',
        color: 'orange',
        percentChanges: {
          today: 7.2,
          yesterday: -3.5,
          week: -1.8,
          month: -4.6,
          year: 22.3
        }
      },
      {
        title: 'Подписки',
        values: {
          today: '48',
          yesterday: '42',
          week: '287',
          month: '1,245',
          year: '7,893'
        },
        icon: 'bx bx-credit-card',
        color: 'blue',
        percentChanges: {
          today: 2.1,
          yesterday: -1.3,
          week: 3.8,
          month: 5.7,
          year: 18.9
        }
      },
      {
        title: 'Рефералы',
        values: {
          today: '27',
          yesterday: '24',
          week: '145',
          month: '628',
          year: '4,291'
        },
        icon: 'bx bx-link',
        color: 'green',
        percentChanges: {
          today: 4.8,
          yesterday: 2.1,
          week: 8.9,
          month: 15.2,
          year: 22.5
        }
      },
      {
        title: 'Новые регистрации',
        values: {
          today: '37',
          yesterday: '32',
          week: '194',
          month: '982',
          year: '8,754'
        },
        icon: 'bx bx-user-plus',
        color: 'purple',
        percentChanges: {
          today: 6.1,
          yesterday: -0.8,
          week: 4.2,
          month: 8.6,
          year: 13.2
        }
      },
      {
        title: 'Активные сессии',
        values: {
          today: '215',
          yesterday: '198',
          week: '1,241',
          month: '5,328',
          year: '42,658'
        },
        icon: 'bx bx-timer',
        color: 'blue',
        percentChanges: {
          today: 3.2,
          yesterday: -1.5,
          week: 4.8,
          month: 6.1,
          year: 9.7
        }
      },
      {
        title: 'Сред. время сессии',
        values: {
          today: '11:28',
          yesterday: '12:05',
          week: '11:52',
          month: '12:43',
          year: '14:21'
        },
        icon: 'bx bx-time',
        color: 'orange',
        percentChanges: {
          today: 1.4,
          yesterday: 0.8,
          week: 2.6,
          month: 3.2,
          year: 7.8
        }
      },
      {
        title: 'Отток пользователей',
        values: {
          today: '1.2%',
          yesterday: '1.5%',
          week: '2.3%',
          month: '3.8%',
          year: '17.2%'
        },
        icon: 'bx bx-log-out-circle',
        color: 'red',
        percentChanges: {
          today: -0.5,
          yesterday: 0.2,
          week: -0.8,
          month: -1.3,
          year: -2.8
        }
      },
      {
        title: 'Конверсия',
        values: {
          today: '26.1%',
          yesterday: '24.5%',
          week: '25.2%',
          month: '24.8%',
          year: '22.1%'
        },
        icon: 'bx bx-trending-up',
        color: 'green',
        percentChanges: {
          today: 1.2,
          yesterday: -0.4,
          week: 1.8,
          month: 2.1,
          year: 0.9
        }
      },
      {
        title: 'Отзывы',
        values: {
          today: '4.8/5',
          yesterday: '4.7/5',
          week: '4.7/5',
          month: '4.7/5',
          year: '4.6/5'
        },
        icon: 'bx bx-star',
        color: 'orange',
        percentChanges: {
          today: 0.1,
          yesterday: 0,
          week: 0.1,
          month: 0.2,
          year: 0.7
        }
      }
    ];
    
    // Возвращаем данные для выбранного периода
    return stats.map(stat => ({
      title: stat.title,
      value: stat.values[periodType],
      icon: stat.icon,
      color: stat.color,
      percentChange: stat.percentChanges[periodType],
      timeframe: basePeriodText[periodType]
    }));
  };

  return (
    <section className="stats-grid-section">
      <div className="stats-header">
        <h2 className="section-heading">Статистика сервиса</h2>
        <div className="period-selector">
          <button 
            className={period === 'today' ? 'active' : ''} 
            onClick={() => setPeriod('today')}
          >
            Сегодня
          </button>
          <button 
            className={period === 'yesterday' ? 'active' : ''} 
            onClick={() => setPeriod('yesterday')}
          >
            Вчера
          </button>
          <button 
            className={period === 'week' ? 'active' : ''} 
            onClick={() => setPeriod('week')}
          >
            Неделя
          </button>
          <button 
            className={period === 'month' ? 'active' : ''} 
            onClick={() => setPeriod('month')}
          >
            Месяц
          </button>
          <button 
            className={period === 'year' ? 'active' : ''} 
            onClick={() => setPeriod('year')}
          >
            Год
          </button>
        </div>
      </div>
      <div className="stats-grid">
        {getStatsByPeriod(period).map((stat, index) => (
          <StatCard
            key={index}
            title={stat.title}
            value={stat.value}
            icon={stat.icon}
            color={stat.color}
            percentChange={stat.percentChange}
            timeframe={stat.timeframe}
          />
        ))}
      </div>
    </section>
  );
};

export default StatsGrid; 