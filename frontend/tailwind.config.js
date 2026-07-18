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
        },
        // Semantic feedback colors — use these instead of raw emerald/amber/rose/blue
        // shades so success/warning/danger/info states stay visually consistent
        // across every screen and are easy to re-theme later.
        success: {
          50: "#ecfdf5",
          100: "#d1fae5",
          200: "#a7f3d0",
          500: "#10b981",
          600: "#059669",
          700: "#047857",
        },
        warning: {
          50: "#fffbeb",
          100: "#fef3c7",
          200: "#fde68a",
          500: "#f59e0b",
          600: "#d97706",
          700: "#b45309",
        },
        danger: {
          50: "#fff1f2",
          100: "#ffe4e6",
          200: "#fecdd3",
          500: "#f43f5e",
          600: "#e11d48",
          700: "#be123c",
        },
        info: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
        },
      },
    },
  },
  plugins: [],
}
