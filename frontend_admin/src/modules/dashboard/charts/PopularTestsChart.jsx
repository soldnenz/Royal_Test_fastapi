import React from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';

Chart.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const data = {
  labels: ['Тест 1', 'Тест 2', 'Тест 3', 'Тест 4', 'Тест 5'],
  datasets: [
    {
      label: 'Количество прохождений',
      data: [10, 20, 15, 25, 30],
      backgroundColor: 'rgba(255, 144, 0, 0.2)',
      borderColor: '#ff9000',
      borderWidth: 2,
    },
  ],
};

const options = {
  responsive: true,
  plugins: {
    legend: { display: false },
    title: { display: true, text: 'Популярные тесты', color: 'var(--main-text)', font: { size: 16 } },
  },
  scales: {
    x: { ticks: { color: 'var(--main-text)' } },
    y: { ticks: { color: 'var(--main-text)' } },
  },
};

const PopularTestsChart = () => <Bar data={data} options={options} />;

export default PopularTestsChart; 