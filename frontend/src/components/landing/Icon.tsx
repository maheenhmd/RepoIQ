import type { ReactNode } from "react";

export type IconName =
  | "github"
  | "code"
  | "layers"
  | "file"
  | "chat"
  | "chart"
  | "target"
  | "graduation"
  | "briefcase"
  | "users"
  | "check"
  | "arrow"
  | "search"
  | "branch"
  | "circle-check";

type Props = {
  name: IconName;
  size?: number;
};

export default function Icon({ name, size = 24 }: Props) {
  const paths: Record<IconName, ReactNode> = {
    github: (
      <>
        <path d="M9 19c-4.3 1.4-4.3-2.5-6-3m12 6v-3.4a3 3 0 0 0-.8-2.3c2.7-.3 5.5-1.3 5.5-6A4.7 4.7 0 0 0 18.4 7 4.3 4.3 0 0 0 18.3 4S17.2 3.7 15 5.6a11 11 0 0 0-6 0C6.8 3.7 5.7 4 5.7 4a4.3 4.3 0 0 0-.1 3A4.7 4.7 0 0 0 4.3 10c0 4.7 2.8 5.7 5.5 6A3 3 0 0 0 9 18.6V22" />
        <path d="M9 22h6" />
      </>
    ),
    code: (
      <path d="m8 6-6 6 6 6m8-12 6 6-6 6M14 4l-4 16" />
    ),
    layers: (
      <path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5" />
    ),
    file: (
      <>
        <path d="M6 2h8l5 5v15H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm8 0v6h5M8 12h8M8 16h8" />
      </>
    ),
    chat: (
      <path d="M20 11.5a8.5 8.5 0 0 1-8.5 8.5 9 9 0 0 1-3.4-.7L3 21l1.7-5A8.5 8.5 0 1 1 20 11.5ZM8 11.5h.01M12 11.5h.01M16 11.5h.01" />
    ),
    chart: (
      <path d="M4 20V12h4v8M10 20V7h4v13M16 20V3h4v17M2 20h20" />
    ),
    target: (
      <>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="5" />
        <circle cx="12" cy="12" r="1" />
        <path d="M12 1v4m0 14v4M1 12h4m14 0h4" />
      </>
    ),
    graduation: (
      <path d="m2 9 10-5 10 5-10 5L2 9Zm4 3v5c3.6 3 8.4 3 12 0v-5M22 9v7" />
    ),
    briefcase: (
      <>
        <rect x="3" y="7" width="18" height="14" rx="2" />
        <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12c5 4 13 4 18 0" />
      </>
    ),
    users: (
      <>
        <circle cx="9" cy="8" r="3" />
        <path d="M2 20v-2a6 6 0 0 1 12 0v2H2Zm15-9a3 3 0 1 0-1-5.8M17 14a5 5 0 0 1 5 5v1h-5" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    search: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 5 5" />
      </>
    ),
    branch: (
      <>
        <circle cx="6" cy="5" r="2" />
        <circle cx="18" cy="19" r="2" />
        <circle cx="6" cy="19" r="2" />
        <path d="M6 7v10m0-5h8a4 4 0 0 1 4 4v1" />
      </>
    ),
    "circle-check": (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="m8 12 3 3 5-6" />
      </>
    ),
  };

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.85"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}