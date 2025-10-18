/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        rostelecom: ['"RostelecomBasis"', 'sans-serif'],
      },
      colors: {
        brand: {
          orange: "#FF4F12",
          light_orange: "#FFF1EC",
          purple: "#F7F0FF",
          lightpurple: "#F7F0FF",
        },
      },
    },
  },
  plugins: [],
};
