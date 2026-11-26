import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        campo: {
          50: "#f3f8f2",
          100: "#e2efdf",
          500: "#4a8a3f",
          600: "#3a7031",
          700: "#2f5a29",
          900: "#1c3519",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
