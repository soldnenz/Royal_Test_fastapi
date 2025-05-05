import React from 'react';
import { Line } from 'react-chartjs-2';
import { Chart, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';

Chart.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const data = {
  labels: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн'],
  datasets: [
    {
      label: 'Доход',
      data: [12000, 19000, 15000, 25000, 22000, 30000],
      fill: true,
      backgroundColor: 'rgba(255, 144, 0, 0.15)',
      borderColor: '#ff9000',
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
    title: { display: true, text: 'Обзор доходов', color: 'var(--main-text)', font: { size: 16 } },
  },
  scales: {
    x: { ticks: { color: 'var(--main-text)' } },
    y: { ticks: { color: 'var(--main-text)' } },
  },
};

const RevenueChart = () => <Line data={data} options={options} />;

export default RevenueChart; 