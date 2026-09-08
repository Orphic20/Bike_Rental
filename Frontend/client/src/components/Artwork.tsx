/*
  Coastal Utility Atelier: warm daylight, editorial asymmetry, restrained clay-red cues.

  These replace the photography the prototype loaded from external storage. A bike
  renders its own `image_url` when the catalogue provides one and falls back to
  line art keyed to its type, so the fleet is never a grid of broken images.
*/
import type { BikeType } from "@/lib/types";

const INK = "#2b4740";
const CLAY = "#c84c3d";

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      className={className ?? "brand-mark-svg"}
      viewBox="0 0 64 64"
      role="img"
      aria-label="Muñoz Bike Rental"
    >
      <circle cx="32" cy="36" r="16" fill="none" stroke="currentColor" strokeWidth="3" />
      <circle cx="32" cy="36" r="4.5" fill={CLAY} />
      <path
        d="M16 36a16 16 0 0 1 32 0"
        fill="none"
        stroke={CLAY}
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path
        d="M32 10v7M48 16l-4.5 4.5M16 16l4.5 4.5"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Distinct silhouettes so the three types stay tellable apart at a glance. */
function BikeGlyph({ type }: { type: BikeType }) {
  if (type === "folding") {
    return (
      <svg viewBox="0 0 320 200" aria-hidden="true">
        <g fill="none" stroke={INK} strokeWidth="4" strokeLinecap="round">
          <circle cx="72" cy="146" r="30" />
          <circle cx="248" cy="146" r="30" />
          <path d="M72 146l46-58h72l30 58" />
          <path d="M118 88h72" />
          <path d="M160 146V88" stroke={CLAY} />
          <path d="M196 74v14M150 66h26" />
          <path d="M108 118h44" />
        </g>
        <circle cx="160" cy="112" r="7" fill={CLAY} />
      </svg>
    );
  }

  if (type === "mountain") {
    return (
      <svg viewBox="0 0 320 200" aria-hidden="true">
        <g fill="none" stroke={INK} strokeWidth="4" strokeLinecap="round">
          <circle cx="70" cy="140" r="38" />
          <circle cx="250" cy="140" r="38" />
          <circle cx="70" cy="140" r="26" strokeWidth="2.5" opacity=".55" />
          <circle cx="250" cy="140" r="26" strokeWidth="2.5" opacity=".55" />
          <path d="M70 140l52-56h76l52 56" />
          <path d="M122 84h76" />
          <path d="M160 140V84" stroke={CLAY} />
          <path d="M198 84V58" />
          <path d="M186 52h26" />
          <path d="M112 76h34" />
        </g>
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 320 200" aria-hidden="true">
      <g fill="none" stroke={INK} strokeWidth="4" strokeLinecap="round">
        <circle cx="70" cy="142" r="34" />
        <circle cx="250" cy="142" r="34" />
        <path d="M70 142q46-52 90-52" />
        <path d="M160 90h44l46 52" />
        <path d="M160 142V90" stroke={CLAY} />
        <path d="M204 90V62M192 56h26" />
        <path d="M112 104h40" />
        <rect x="196" y="62" width="42" height="28" rx="3" stroke={CLAY} strokeWidth="3" />
      </g>
    </svg>
  );
}

export function BikeArt({
  type,
  imageUrl,
  alt,
}: {
  type: BikeType | null;
  imageUrl?: string | null;
  alt: string;
}) {
  const tone = type ?? "japanese";
  if (imageUrl) {
    return (
      <span className={`bike-art tone-${tone}`}>
        <img src={imageUrl} alt={alt} loading="lazy" />
      </span>
    );
  }
  return (
    <span className={`bike-art tone-${tone}`} role="img" aria-label={alt}>
      <BikeGlyph type={tone} />
    </span>
  );
}

export function HeroArt() {
  return (
    <div className="hero-art-canvas" role="img" aria-label="A bike on a sunlit coastal street">
      <svg viewBox="0 0 600 700" aria-hidden="true">
        <circle cx="430" cy="150" r="86" fill="#f2d9ae" opacity=".85" />
        <g fill="none" stroke="#fdf6e8" strokeWidth="2" opacity=".5">
          <path d="M0 470q150-70 300 0t300 0" />
          <path d="M0 520q150-70 300 0t300 0" />
          <path d="M0 570q150-70 300 0t300 0" />
        </g>
        <g fill="none" stroke="#20342c" strokeWidth="7" strokeLinecap="round" opacity=".92">
          <circle cx="188" cy="470" r="72" />
          <circle cx="418" cy="470" r="72" />
          <path d="M188 470l104-118h86l40 118" />
          <path d="M292 352h86" />
          <path d="M303 470V352" stroke={CLAY} />
          <path d="M378 352v-52M356 292h48" />
          <path d="M244 412h84" />
        </g>
        <circle cx="303" cy="470" r="13" fill={CLAY} />
      </svg>
    </div>
  );
}
