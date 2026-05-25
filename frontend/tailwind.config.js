import tailwindcss from 'tailwindcss'
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          base: '#282c34',
          surface: '#343b47',
          accent: '#4b566a'
        },
        fg: {
          primary: '#f8f8f2',
          secondary: '#d1d5da',
          muted: '#9ca0aa'
        }
      }
    },
  },
}
