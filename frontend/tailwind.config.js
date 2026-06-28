/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        figtree: ["var(--font-figtree)", "sans-serif"],
        sans: ["var(--font-figtree)", "sans-serif"],
      },
      colors: {
        brand: {
          dark: "#061329",      // Sidebar background
          darkHover: "#0e203e", // Sidebar hover states
          blue: "#1e62ec",      // Active state vibrant blue
          blueHover: "#164fc2", // Active hover blue
          textMuted: "#94a3b8", // Gray text in sidebar
        },
        dashboard: {
          bg: "#f8fafc",        // Light slate layout bg
          card: "#ffffff",      // White card bg
          border: "#e2e8f0",    // Divider lines border
          text: "#0f172a",      // Main text slate-900
        }
      },
    },
  },
  plugins: [],
}
