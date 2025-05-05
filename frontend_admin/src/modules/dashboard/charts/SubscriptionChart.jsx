import React from 'react';
import { Doughnut } from 'react-chartjs-2';
import { Chart, ArcElement, Tooltip, Legend, Title } from 'chart.js';

Chart.register(ArcElement, Tooltip, Legend, Title);

const data = {
  labels: ['Базовый', 'Стандарт', 'Премиум'],
  datasets: [
    {
      data: [300, 150, 100],
      backgroundColor: ['#ff9000', '#54a0ff', '#ffd700'],
      borderWidth: 2,
    },
  ],
};

const options = {
  responsive: true,
  plugins: {
    legend: { position: 'bottom', labels: { color: 'var(--main-text)' } },
    title: { display: true, text: 'Распределение подписок', color: 'var(--main-text)', font: { size: 16 } },
  },
};

const SubscriptionChart = () => <Doughnut data={data} options={options} />;

export default SubscriptionChart; 