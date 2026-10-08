/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Bottle green rather than black: Kumü's documents are read, printed
        // and defended in meetings, and ink that carries the brand costs
        // nothing in legibility.
        ink: { DEFAULT: '#0F2E22', soft: '#3D5A4C', faint: '#7C9387' },
        paper: { DEFAULT: '#FBFCFB', sunk: '#F3F6F4' },
        field: { DEFAULT: '#1A7A4C', dark: '#145F3B', wash: '#E8F2EC' },
        rule: { DEFAULT: '#DCE4DF', strong: '#B9C8C0' },
        // One warm accent, reserved for provenance caveats. Never decorative.
        flag: { DEFAULT: '#9A5B0B', wash: '#FDF6EC' },
      },
      fontFamily: {
        display: ['Newsreader', 'Georgia', 'serif'],
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        // A scale, not arbitrary steps: 1.25 ratio from a 16px base.
        'data-xl': ['3.5rem', { lineHeight: '1', letterSpacing: '-0.02em' }],
        'data-lg': ['2.25rem', { lineHeight: '1.1', letterSpacing: '-0.01em' }],
      },
      maxWidth: { read: '68ch' },
    },
  },
  plugins: [],
}
