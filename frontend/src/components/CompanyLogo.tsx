import { useState } from "react";

import { avatarColor, cn, initials } from "../lib/format";

type LogoSize = "sm" | "md" | "lg";

const SIZES: Record<LogoSize, string> = {
  sm: "h-8 w-8 text-[11px]",
  md: "h-10 w-10 text-xs",
  lg: "h-14 w-14 text-sm",
};

interface CompanyLogoProps {
  name: string;
  logoUrl?: string | null;
  size?: LogoSize;
  className?: string;
}

/**
 * Company mark with a deterministic initials fallback. Logos are loaded from
 * the company registry and never generated.
 */
export function CompanyLogo({ name, logoUrl, size = "md", className }: CompanyLogoProps) {
  const [failed, setFailed] = useState(false);
  const showImage = Boolean(logoUrl) && !failed;

  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-200 font-semibold",
        SIZES[size],
        showImage ? "bg-white" : avatarColor(name),
        className,
      )}
      aria-hidden={showImage ? undefined : true}
    >
      {showImage ? (
        <img
          src={logoUrl as string}
          alt=""
          className="h-full w-full object-contain p-1"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        initials(name)
      )}
    </div>
  );
}
