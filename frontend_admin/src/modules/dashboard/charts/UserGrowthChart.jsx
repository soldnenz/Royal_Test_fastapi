import React from 'react';
import { Line } from 'react-chartjs-2';
import { Chart, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';

Chart.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const data = {
  labels: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
  datasets: [
    {
      label: 'Новые пользователи',
      data: [65, 59, 80, 81, 56, 55, 40],
      fill: false,
      borderColor: '#ff9000',
      backgroundColor: '#ff9000',
      tension: 0.3,
      pointRadius: 4,
      pointHoverRadius: 6,
    },
  ],
};

const options = {
  responsive: true,
  plugins: {
    legend: { display: false },
    title: { display: true, text: 'Рост пользователей', color: 'var(--main-text)', font: { size: 18 } },
  },
  scales: {
    x: { ticks: { color: 'var(--main-text)' } },
    y: { ticks: { color: 'var(--main-text)' } },
  },
};

const UserGrowthChart = () => <Line data={data} options={options} />;

export default UserGrowthChart; 