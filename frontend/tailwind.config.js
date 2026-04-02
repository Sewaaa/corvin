/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        corvin: {
          950: '#08080f',
          900: '#0f0f1a',
          800: '#1a1a2e',
          700: '#25253e',
          600: '#30305a',
          accent: '#7c3aed',
          'accent-light': '#a855f7',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
