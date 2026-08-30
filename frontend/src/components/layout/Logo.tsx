export function Logo({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="2" y="2" width="20" height="20" rx="5" fill="#17233D" stroke="#2D3748" />
      <path d="M8.5 8L5.5 12L8.5 16" stroke="#7FADFF" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M15.5 8L18.5 12L15.5 16" stroke="#7FADFF" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="1.4" fill="#4C8DFF" />
    </svg>
  );
}
