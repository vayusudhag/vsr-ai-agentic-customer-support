/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#131B2E", 2: "#1C2640", 3: "#2A3655", muted: "#8A94AD" },
        paper: "#F5F6F8",
        line: "#E3E6EC",
        lagoon: { DEFAULT: "#0F766E", 600: "#0D6660", soft: "#E3F2EF", ink: "#0B4F4A" },
        amber: { DEFAULT: "#B7791F", soft: "#FCF1DC", ink: "#7A4E0E" },
        alert: { DEFAULT: "#B42318", soft: "#FDECEA" },
        agent: { supervisor: "#475569", order: "#2563EB", knowledge: "#0F766E", returns: "#B7791F", product: "#7C3AED" },
      },
      fontFamily: {
        display: ['"Sora"', "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      boxShadow: { lift: "0 1px 2px rgba(19,27,46,.06), 0 8px 24px -12px rgba(19,27,46,.18)" },
    },
  },
  plugins: [],
};
