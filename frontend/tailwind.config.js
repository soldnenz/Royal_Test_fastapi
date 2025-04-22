/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#D4AF37', // Golden
          50: '#FCF9EB',
          100: '#F9F3D7',
          200: '#F3E7AF',
          300: '#ECDA87',
          400: '#E6CE5F',
          500: '#DFC237', // Default golden
          600: '#D4AF37',
          700: '#B89128',
          800: '#9C741E',
          900: '#805714',
        },
        secondary: {
          DEFAULT: '#7B61FF', // Rich Purple
          50: '#F3F0FF',
          100: '#E8E0FF',
          200: '#D0C2FF',
          300: '#B9A3FF',
          400: '#A182FF',
          500: '#8A61FF',
          600: '#7B61FF',
          700: '#6247E0',
          800: '#4A31C1',
          900: '#322091',
        },
        accent: {
          DEFAULT: '#1E88E5', // Bright Blue
          50: '#E3F2FD',
          100: '#BBDEFB',
          200: '#90CAF9',
          300: '#64B5F6',
          400: '#42A5F5',
          500: '#2196F3',
          600: '#1E88E5',
          700: '#1976D2',
          800: '#1565C0',
          900: '#0D47A1',
        },
        dark: {
          DEFAULT: '#1E293B', // Slate dark
          50: '#F8FAFC',
          100: '#F1F5F9',
          200: '#E2E8F0',
          300: '#CBD5E1',
          400: '#94A3B8',
          500: '#64748B',
          600: '#475569',
          700: '#334155',
          800: '#1E293B',
          900: '#0F172A',
        },
        light: {
          DEFAULT: '#F8FAFC', // Slate light
          50: '#FFFFFF',
          100: '#F8FAFC',
          200: '#F1F5F9',
          300: '#E2E8F0',
          400: '#CBD5E1',
          500: '#94A3B8',
          600: '#64748B',
          700: '#475569',
          800: '#334155',
          900: '#1E293B',
        },
        darkOverride: {
          card: 'rgba(30, 41, 59, 0.95)',
          background: '#0f172a',
          surface: '#1e293b',
          text: 'rgba(255, 255, 255, 0.9)',
        }
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: 0, transform: 'translateY(-10px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
        pulse: {
          '0%, 100%': { opacity: 1 },
          '50%': { opacity: 0.8 },
        }
      },
      animation: {
        fadeIn: 'fadeIn 0.3s ease-out',
        pulse: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  darkMode: 'class',
  plugins: [],
} 