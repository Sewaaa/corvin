/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        corvin: {
          50:  '#F7F7FD',
          100: '#EEEDF9',
          200: '#D9D7F4',
          300: '#BDB9EC',
          nav: '#0B0D16',
          'nav-hover': '#161929',
          'nav-active': '#7C3AED',
          accent: '#7C3AED',
          'accent-light': '#8B5CF6',
          'accent-dark': '#6D28D9',
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
