/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#EFF6FF',
          100: '#DBEAFE',
          200: '#BFDBFE',
          300: '#93C5FD',
          400: '#60A5FA',
          500: '#3B82F6',
          600: '#2563EB',
          700: '#1D4ED8',
          800: '#1E40AF',
          900: '#1E3A8A',
          950: '#172554',
        },
        surface: {
          50:  '#FAFAFA',
          100: '#F4F6F8',
          200: '#E8ECF0',
          300: '#D1D8E0',
          400: '#94A3B8',
          500: '#64748B',
          600: '#475569',
          700: '#334155',
          800: '#1E293B',
          900: '#0F172A',
        },
        navy: {
          700: '#1E293B',
          800: '#172035',
          900: '#0F1729',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],   // 10px
        'xs':  ['0.75rem',  { lineHeight: '1rem'    }],   // 12px
        'sm':  ['0.8125rem',{ lineHeight: '1.25rem' }],   // 13px
        'base':['0.9375rem',{ lineHeight: '1.5rem'  }],   // 15px
        'lg':  ['1.0625rem',{ lineHeight: '1.625rem'}],   // 17px
        'xl':  ['1.125rem', { lineHeight: '1.75rem' }],   // 18px
        '2xl': ['1.25rem',  { lineHeight: '1.875rem'}],   // 20px
        '3xl': ['1.5rem',   { lineHeight: '2rem'    }],   // 24px
        '4xl': ['1.875rem', { lineHeight: '2.25rem' }],   // 30px
        '5xl': ['2.25rem',  { lineHeight: '2.5rem'  }],   // 36px
      },
      boxShadow: {
        'card':  '0 1px 3px 0 rgba(0,0,0,0.06), 0 1px 2px -1px rgba(0,0,0,0.04)',
        'panel': '0 4px 16px 0 rgba(0,0,0,0.06)',
        'float': '0 8px 24px 0 rgba(0,0,0,0.10)',
      },
      borderRadius: {
        'xl': '0.75rem',
        '2xl': '1rem',
      },
    },
  },
  plugins: [],
};
