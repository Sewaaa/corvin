/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        corvin: {
          50:  '#f7f8fc',
          100: '#eef0f7',
          200: '#dde1ef',
          300: '#bcc3d9',
          nav: '#1e2235',
          'nav-hover': '#2a3050',
          'nav-active': '#2563eb',
          accent: '#2563eb',
          'accent-light': '#3b82f6',
          'accent-dark': '#1d4ed8',
        },
      },
      fontFamily: {
        sans: ['Figtree', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.04)',
        'card-md': '0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.05)',
      },
    },
  },
  plugins: [],
};
