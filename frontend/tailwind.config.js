import tailwindcss from 'tailwindcss'
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        wave: {
          950: '#080b12',
          900: '#0d1117',
          800: '#151b27',
          700: '#1e2638',
          600: '#28334a',
          500: '#36445e',
          400: '#4a5a78',
          300: '#6b7fa0',
          200: '#9aafc8',
          100: '#cdd8e8',
          50:  '#edf1f7',
        },
        teal: {
          400: '#2dd4bf',
          300: '#5eead4',
          200: '#99f6e4',
        },
        emerald: {
          500: '#10b981',
          400: '#34d399',
          300: '#6ee7b7',
        },
        amber: {
          500: '#f59e0b',
          400: '#fbbf24',
          300: '#fcd34d',
        },
        rose: {
          500: '#f43f5e',
          400: '#fb7185',
          300: '#fda4af',
        },
        sky: {
          400: '#38bdf8',
          300: '#7dd3fc',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          'sans-serif',
        ],
        mono: [
          '"JetBrains Mono"',
          '"Fira Code"',
          'ui-monospace',
          'monospace',
        ],
      },
      borderRadius: {
        card: '12px',
        badge: '6px',
      },
      boxShadow: {
        card:  '0 2px 12px 0 rgba(0,0,0,0.45)',
        glow:  '0 0 16px 0 rgba(45,212,191,0.18)',
        panel: '0 1px 4px 0 rgba(0,0,0,0.6)',
      },
    },
  },
}
