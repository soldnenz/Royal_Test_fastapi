# RoyalHub Admin Frontend (React + Vite)

This is the new modular admin dashboard for RoyalHub, built with React and Vite for fast development and modern best practices.

## Structure
- **src/pages/**: Main pages (Dashboard, Users, Tests)
- **src/components/**: Reusable UI components (cards, tables, modals, etc.)
- **src/modules/**: Feature modules (User management, Statistics, Test management)
- **src/styles/**: Global and modular styles

## Main Pages
- **Dashboard**: Statistics, charts, and quick overview
- **Users**: User list, search, details, balance, subscription, ban management
- **Tests**: Test list, test management, results

## Development
```bash
npm install
npm run dev
```

---
This project is a work in progress. The UI/UX is based on the previous HTML admin pages: `dashboard.html`, `dashboard_user.html`, and `admin_dashboard_test_check.html`.

# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
