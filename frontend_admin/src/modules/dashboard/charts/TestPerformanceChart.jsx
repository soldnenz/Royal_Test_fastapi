import React from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';

Chart.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const data = {
  labels: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн'],
  datasets: [
    {
      label: 'Средний балл',
      data: [65, 59, 80, 81, 56, 55],
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
    title: { display: true, text: 'Результаты тестов', color: 'var(--main-text)', font: { size: 16 } },
  },
  scales: {
    x: { ticks: { color: 'var(--main-text)' } },
    y: { ticks: { color: 'var(--main-text)' } },
  },
};

const TestPerformanceChart = () => <Bar data={data} options={options} />;

export default TestPerformanceChart; 