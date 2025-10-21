// frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./contexts/**/*.{js,ts,jsx,tsx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        inter: ['Inter', 'sans-serif'],
      },
      colors: {
        /*
         * Redefined the color palette to better align with the "soft and comfortable" design aesthetic,
         * introducing more soft blues, purples, and grays, while maintaining necessary contrast.
         * The primary color group will lean towards softer blues.
         * Added a new palette-purple group to provide colors that better fit our soft purple tones.
         */
        primary: {
          DEFAULT: '#6A8BFF', // A softer, more inviting blue
          light: '#A3B9FF',    // Lighter shade for highlights
          dark: '#4767D9',     // Darker shade for contrast
          lighter: '#EBF2FF',  // Very light background
        },
        accent: {
          DEFAULT: '#9C7AFF', // A soft, pleasing purple
          light: '#C7B3FF',    // Lighter accent
          dark: '#7D5CD9',     // Darker accent
        },
        'palette-purple': {
          light: '#A490E0',    // Softer purple for selected background
          DEFAULT: '#886CCF',  // Default purple for accents
          dark: '#6C48B0',     // Darker purple for selected border/text
          lighten: '#BEACF1',  // Lighter hover state for selected
          darker: '#5A3A91',   // Darker hover state for selected border
        },
        gray: {
          50: '#F5F7FA', 
          100: '#EAEFF4',
          200: '#D5DCE4',
          300: '#B0B8C4',
          400: '#8A94A0',
          500: '#656D7A',
          600: '#404651', 
          700: '#2A303A', 
          800: '#1A202C', 
          900: '#10141B',
        },

        // General purpose 
        softBg: '#F5F7FA', 
        white: '#FFFFFF',
        black: '#000000',
        red: {
          600: '#DC2626', // Keep standard red for errors
        }
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic":
          "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
      },
      // --- START: New additions for animations ---
      keyframes: {
        // Spinner animation with subtle breathing
        'breathe-spin': {
          '0%, 100%': { transform: 'rotate(0deg) scale(0.95)', opacity: '0.8' },
          '50%': { transform: 'rotate(180deg) scale(1.05)', opacity: '1' },
        },
        // Dot animation for "..." in messages
        'blink': {
          '0%, 100%': { opacity: '0' },
          '50%': { opacity: '1' },
        },
        // Subtle pulse for general UI elements
        'pulse-subtle': {
          '0%, 100%': { transform: 'scale(1)', opacity: '1' },
          '50%': { transform: 'scale(1.01)', opacity: '0.98' }, // Slightly larger, slightly less opaque
        },
        'pulse-select': {
          '0%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.03)' },
          '100%': { transform: 'scale(1)' },
        },
        // Breathing light effect for liquid glass elements
        'breathe-light': {
          '0%, 100%': { boxShadow: '0 0 10px rgba(255, 255, 255, 0.05)' },
          '50%': { boxShadow: '0 0 20px rgba(255, 255, 255, 0.15)' }, // More pronounced glow
        },
      },
      animation: {
        'breathe-spin': 'breathe-spin 2s ease-in-out infinite',
        'blink': 'blink 1s steps(1, end) infinite',
        'pulse-subtle': 'pulse-subtle 3s ease-in-out infinite', // Slower, more subtle pulse
        'breathe-light': 'breathe-light 4s ease-in-out infinite', // Slower, gentle light effect
        'pulse-select': 'pulse-select 0.3s ease-out 1',
      },
      animationDelay: { // Custom animation delays for staggered effects
        '100': '100ms',
        '200': '200ms',
        '300': '300ms',
        '400': '400ms',
        '500': '500ms',
        '600': '600ms',
        // Add more as needed
      },
      // --- END: New additions for animations ---
    },
  },
  plugins: [],
};