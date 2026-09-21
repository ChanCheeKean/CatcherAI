import { labelStyle } from './graphModel'

// 20x20 line icons; the stroke is set by the caller.
const shapes = {
  person: <><circle cx="10" cy="7" r="3" /><path d="M4 16c0-3 3-5 6-5s6 2 6 5" /></>,
  wallet: <><rect x="3" y="5" width="14" height="10" rx="1.5" /><path d="M3 8h14M13 11.5h2" /></>,
  card: <><rect x="2.5" y="5" width="15" height="10" rx="1.5" /><path d="M2.5 8.5h15M5 12h3" /></>,
  key: <><circle cx="7" cy="10" r="3" /><path d="M10 10h7M14 10v3" /></>,
  device: <><rect x="5" y="3" width="10" height="14" rx="1.5" /><path d="M9 14.5h2" /></>,
  globe: <><circle cx="10" cy="10" r="7" /><path d="M3 10h14M10 3c-3 3-3 11 0 14M10 3c3 3 3 11 0 14" /></>,
  phone: <path d="M6 3h3l1 4-2 1.5a9 9 0 0 0 3.5 3.5L13 10l4 1v3a2 2 0 0 1-2 2C9 16 4 11 4 5a2 2 0 0 1 2-2z" />,
  mail: <><rect x="3" y="5" width="14" height="10" rx="1.5" /><path d="M3 6l7 5 7-5" /></>,
  house: <path d="M3 10l7-6 7 6M5 9v7h10V9" />,
  swap: <path d="M4 7h11l-3-3M16 13H5l3 3" />,
  shield: <path d="M10 3l6 2v5c0 4-3 6-6 7-3-1-6-3-6-7V5z" />,
  shop: <path d="M3 8l1-4h12l1 4M4 8v8h12V8M8 16v-4h4v4" />,
  terminal: <><rect x="3" y="4" width="14" height="10" rx="1.5" /><path d="M7 17h6M10 14v3" /></>,
  tag: <><path d="M3 10V4h6l8 8-6 6z" /><circle cx="6.5" cy="7.5" r="1" /></>,
  box: <path d="M3 6l7-3 7 3v8l-7 3-7-3zM3 6l7 3 7-3M10 9v8" />,
  truck: <><path d="M2 5h10v8H2zM12 8h4l2 3v2h-6" /><circle cx="6" cy="14" r="1.5" /><circle cx="14" cy="14" r="1.5" /></>,
  bot: <><rect x="4" y="7" width="12" height="9" rx="2" /><path d="M10 7V4M8 11h.01M12 11h.01" /></>,
  scroll: <path d="M6 3h9v11a3 3 0 0 1-3 3H5a2 2 0 0 0 2-2V3M6 3a2 2 0 0 0-2 2v1h2M9 7h4M9 10h4" />,
  flag: <path d="M5 17V3M5 4h10l-2 3.5 2 3.5H5" />,
  doc: <path d="M5 3h7l3 3v11H5zM12 3v3h3M8 10h4M8 13h4" />,
  question: <><circle cx="10" cy="10" r="7" /><path d="M8 8a2 2 0 1 1 3 1.7c-.7.5-1 .9-1 1.8M10 14.5h.01" /></>,
  chat: <path d="M3 4h14v9H9l-4 3v-3H3z" />,
  bolt: <path d="M11 2L4 11h5l-1 7 7-9h-5z" />,
  note: <path d="M4 4h12v9l-3 3H4zM13 16v-3h3M7 8h6M7 11h3" />,
  spark: <path d="M10 2l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" />,
}

export function Icon({ label, size = 18 }: { label: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 20 20"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {shapes[labelStyle(label).icon]}
    </svg>
  )
}
