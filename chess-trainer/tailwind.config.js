/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'sky-blue': '#87CEEB',
        'sunny-yellow': '#FFE066',
        'grass-green': '#7CB342',
        'cream': '#FFF8DC',
        'light-green': '#C5E1A5',
        'dark-blue': '#1A237E',
        'purple': '#5E35B1',
        'success': '#4CAF50',
        'warning': '#FF9800',
        'error': '#EF5350',
      },
      fontFamily: {
        'comic': ['"Comic Neue"', 'Nunito', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
