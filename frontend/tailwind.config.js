/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
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
        // Premium dark theme, scoped to the Dashboard home page redesign only —
        // intentionally namespaced separately from `dashboard.*` so no other
        // (still light-themed) page is affected by this palette.
        dashDark: {
          bg: "#0a1120",        // Page background — deep navy
          card: "#111b30",      // Card surface
          cardAlt: "#0d1626",   // Nested/inset surface (slightly darker than card)
          border: "rgba(255,255,255,0.08)",
          borderStrong: "rgba(255,255,255,0.14)",
          text: "#f1f5f9",      // Primary text (slate-100)
          textMuted: "#94a3b8", // Secondary text (slate-400)
          textFaint: "#64748b", // Tertiary text (slate-500)
        }
      },
    },
  },
  plugins: [],
}
