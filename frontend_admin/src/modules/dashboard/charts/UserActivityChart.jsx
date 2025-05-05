import React from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';

Chart.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const data = {
  labels: ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
  datasets: [
    {
      label: 'Количество активных пользователей',
      data: [10, 15, 12, 18, 20, 15, 10],
      backgroundColor: 'rgba(84, 160, 255, 0.2)',
      borderColor: '#54a0ff',
      borderWidth: 2,
    },
  ],
};

const options = {
  responsive: true,
  plugins: {
    legend: { display: false },
    title: { display: true, text: 'Активность пользователей', color: 'var(--main-text)', font: { size: 16 } },
  },
  scales: {
    x: { ticks: { color: 'var(--main-text)' } },
    y: { ticks: { color: 'var(--main-text)' } },
  },
};

const UserActivityChart = () => <Bar data={data} options={options} />;

export default UserActivityChart; 