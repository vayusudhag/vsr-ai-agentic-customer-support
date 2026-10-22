export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="16" fill="#131B2E" />
      <path d="M17 19 L32 46 L47 19" fill="none" stroke="#5EC4B6" strokeWidth="5.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="17" cy="19" r="5" fill="#F5F6F8" />
      <circle cx="47" cy="19" r="5" fill="#F5F6F8" />
      <circle cx="32" cy="46" r="5.5" fill="#F2B544" />
    </svg>
  );
}

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className={light ? "rounded-[10px] ring-1 ring-white/15" : ""}><LogoMark /></span>
      <span className={`font-display text-[17px] font-semibold tracking-tight ${light ? "text-white" : "text-ink"}`}>
        VSR<span className={light ? "text-[#5EC4B6]" : "text-lagoon"}> AI</span>
      </span>
    </span>
  );
}
