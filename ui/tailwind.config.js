/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          base:    "#0B0D12",
          surface: "#11141B",
          raised:  "#161A22",
          border:  "#1F2330",
        },
        accent: {
          DEFAULT: "#8B7DFF",
          hover:   "#9D90FF",
          muted:   "rgba(139,125,255,0.14)",
        },
        cy: {
          DEFAULT: "#5DE3FF",
          soft:    "rgba(93,227,255,0.12)",
        },
        tx: {
          primary:   "#ECEDEF",
          secondary: "#A8AEBB",
          muted:     "#6E7689",
          code:      "#5DE3FF",
        },
        sev: {
          error:   "#F47272",
          warning: "#F2B45A",
          healthy: "#5BD6A8",
          info:    "#7AB8FF",
        },
      },
      fontFamily: {
        sans:    ["Geist", "Inter", "system-ui", "sans-serif"],
        mono:    ["Geist Mono", "JetBrains Mono", "monospace"],
        serif:   ["Instrument Serif", "Georgia", "serif"],
      },
      fontSize: {
        xs:   ["11px", { lineHeight: "16px", letterSpacing: "0.04em" }],
        sm:   ["12px", { lineHeight: "18px" }],
        base: ["13px", { lineHeight: "20px" }],
        lg:   ["16px", { lineHeight: "24px" }],
        xl:   ["22px", { lineHeight: "28px" }],
      },
    },
  },
  plugins: [],
};
