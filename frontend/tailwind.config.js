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
        // CANCHA — the palette comes off a pitch seen in daylight, not off a
        // broadcast. Grass is dusty, lines are chalk, and the only saturated
        // colours in the system belong to data.
        //
        // Ink is almost black with a green cast: it prints, and it never
        // competes with the accents for attention.
        ink: { DEFAULT: '#1B1F1A', soft: '#3A3D38', faint: '#5C5F56' },
        // Chalk ground. Nothing here is pure white: paper.card is the raised
        // surface, paper.sunk the recessed one.
        paper: { DEFAULT: '#F2F1EA', card: '#FBFAF5', sunk: '#E9E8DE' },
        // Grass is a FILL, never a text colour and never a button. Its only
        // job is to be the pitch under a spatial figure.
        grass: { DEFAULT: '#C8CFBE', shade: '#9BA68C', line: '#FBFAF5' },
        // THE TWO DATA SERIES. Clay is A, slate is B. They differ in hue AND
        // in lightness, so a comparison survives greyscale printing and
        // colour-blind readers — clubs print, and the chart has to hold.
        clay: { DEFAULT: '#C25A3A', ink: '#A6462A', wash: '#F7E8E2' },
        slate: { DEFAULT: '#3A5A7A', ink: '#2F4A66', wash: '#E6EBF1' },
        // Chrome: buttons, focus rings, the primary action. Ink, not an
        // accent — the accents are spoken for by the data.
        field: { DEFAULT: '#1B1F1A', dark: '#0E110D', wash: '#E9E8DE' },
        rule: { DEFAULT: '#D8D7CC', strong: '#B6B4A6' },
        // PROVENANCE, and nothing else. Deliberately not clay: a reader must
        // never have to ask whether an underline means "estimated" or
        // "player A". flag.mark is the underline, flag.DEFAULT the text.
        flag: { DEFAULT: '#8A5E14', mark: '#B07A20', wash: '#F7F1E2' },
        // Direction in the market table, where the sign is read before the
        // figure. Nowhere else: a falling price is not an error.
        loss: { DEFAULT: '#A3372B', wash: '#F8EDEB' },
      },
      fontFamily: {
        // Display carries the figure and the headline. Nobody in football
        // analytics uses it, which is the cheapest differentiation there is.
        display: ['"Bricolage Grotesque"', 'system-ui', 'sans-serif'],
        sans: ['Archivo', 'system-ui', 'sans-serif'],
        // Condensed caps for every label and axis. The sports-lettering
        // heritage is the point, and it buys horizontal room in dense tables.
        label: ['"Archivo Narrow"', 'Archivo', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        // The jump from label to figure is deliberate and large: at a glance
        // there is never a question about which number is the answer.
        'data-xl': ['4.5rem', { lineHeight: '0.9', letterSpacing: '-0.045em' }],
        'data-lg': ['3.5rem', { lineHeight: '0.92', letterSpacing: '-0.04em' }],
        'data-md': ['2.125rem', { lineHeight: '1', letterSpacing: '-0.03em' }],
        label: ['0.6875rem', { lineHeight: '1.2', letterSpacing: '0.16em' }],
      },
      gridTemplateColumns: {
        // The pitch Kumü already computes: six columns by four bands. A panel
        // on a spatial screen does not get an arbitrary width — it occupies
        // zones. See .grid-doc in globals.css for screens with no geography.
        zones: 'repeat(6, minmax(0, 1fr))',
        doc: 'repeat(12, minmax(0, 1fr))',
      },
      gridTemplateRows: {
        bands: 'repeat(4, minmax(0, 1fr))',
      },
      maxWidth: { read: '68ch' },
    },
  },
  plugins: [],
}
