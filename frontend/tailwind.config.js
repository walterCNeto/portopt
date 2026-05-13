/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Brand: WCN Softwares + tier coloring
        wcn: {
          primary: "#0F4C81",
          accent: "#E07B00",
          ink: "#1A1A2E",
        },
        tier: {
          naive: "#94A3B8",
          allocation: "#3B82F6",
          alt_risk: "#8B5CF6",
          risk_budget: "#10B981",
          robust: "#F59E0B",
          roadmap: "#6B7280",
        },
      },
      fontFamily: {
        serif: ["Lora", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
