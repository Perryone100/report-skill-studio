import type { SVGProps } from 'react'

export type IconName =
  | 'briefcase'
  | 'calendar'
  | 'check'
  | 'chevron'
  | 'document'
  | 'download'
  | 'edit'
  | 'plus'
  | 'refresh'
  | 'settings'
  | 'sparkle'
  | 'warning'

const paths: Record<IconName, React.ReactNode> = {
  briefcase: <path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7m-9 0h12a1 1 0 0 1 1 1v9a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V8a1 1 0 0 1 1-1Zm-1 5h14M10 11v2h4v-2" />,
  calendar: <path d="M7 3v3m10-3v3M5 9h14M6 5h12a1 1 0 0 1 1 1v13H5V6a1 1 0 0 1 1-1Zm3 8h2m2 0h2m-6 3h2m2 0h2" />,
  check: <path d="m5 12 4 4L19 6" />,
  chevron: <path d="m9 18 6-6-6-6" />,
  document: <path d="M7 3h7l4 4v14H7V3Zm7 0v5h4M10 12h5m-5 4h5" />,
  download: <path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14" />,
  edit: <path d="m14 5 5 5M4 20l3.5-.8L18.2 8.5a1.5 1.5 0 0 0 0-2.1l-.6-.6a1.5 1.5 0 0 0-2.1 0L4.8 16.5 4 20Z" />,
  plus: <path d="M12 5v14m-7-7h14" />,
  refresh: <path d="M20 7v5h-5M4 17v-5h5m10.1-3A8 8 0 0 0 5.4 6M4.9 15A8 8 0 0 0 18.6 18" />,
  settings: <path d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Zm7-3.2 2-1-2-3.5-2.1.7a7.4 7.4 0 0 0-1.6-.9L15 5h-4l-.4 2.3a7.4 7.4 0 0 0-1.5.9L7 7.5 5 11l2 1a7 7 0 0 0 0 1.8l-2 1L7 18.5l2.1-.7a7.4 7.4 0 0 0 1.5.9L11 21h4l.3-2.3a7.4 7.4 0 0 0 1.6-.9l2.1.7 2-3.6-2-1a7 7 0 0 0 0-1.9Z" />,
  sparkle: <path d="m12 3 1.4 4.1L17.5 8.5l-4.1 1.4L12 14l-1.4-4.1-4.1-1.4 4.1-1.4L12 3Zm6 11 .7 2.3L21 17l-2.3.7L18 20l-.7-2.3L15 17l2.3-.7L18 14Z" />,
  warning: <path d="M12 4 3.5 19h17L12 4Zm0 5v5m0 3h.01" />,
}

export function Icon({ name, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {paths[name]}
    </svg>
  )
}
