import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import "./appearance.css";
import "./saas-design.css";

export type Appearance = {
  preset: "workspace" | "paper" | "stone" | "baseline";
  accent: string;
  fontScale: number;
  density: "comfortable" | "compact";
  radius: number;
  heading: "serif" | "sans";
};
// Preserve earlier preferences; the KT color system has its own defaults.
export const APPEARANCE_KEY = "klink:hr:appearance:v3";
export const APPEARANCE_EVENT = "klink:appearance-saved";
export const DEFAULT_APPEARANCE: Appearance = {
  preset: "workspace",
  accent: "#D91F2B",
  fontScale: 1,
  density: "comfortable",
  radius: 12,
  heading: "sans",
};
export const PRESETS = [
  {
    id: "workspace",
    name: "KT 워크스페이스",
    description: "KT 레드 · 블랙 · 화이트",
    canvas: "#F6F6F7",
    side: "#FFFFFF",
    accent: "#D91F2B",
  },
  {
    id: "paper",
    name: "페이퍼",
    description: "따뜻한 바탕 · 테라코타",
    canvas: "#F8F6F0",
    side: "#EEECE4",
    accent: "#A65035",
  },
  {
    id: "stone",
    name: "스톤",
    description: "차분한 회색 · 세이지",
    canvas: "#F5F6F3",
    side: "#E9EDE8",
    accent: "#3D6255",
  },
  {
    id: "baseline",
    name: "기존 시안",
    description: "보존된 네이비 · 블루",
    canvas: "#F5F7FA",
    side: "#1C293E",
    accent: "#3D629B",
  },
] as const;

export function normalizeAppearance(value: unknown): Appearance {
  const data =
    value && typeof value === "object"
      ? (value as Record<string, unknown>)
      : {};
  return {
    preset:
      data.preset === "baseline" ||
      data.preset === "stone" ||
      data.preset === "paper"
        ? data.preset
        : "workspace",
    accent:
      typeof data.accent === "string" && /^#[a-f\d]{6}$/i.test(data.accent)
        ? data.accent
        : DEFAULT_APPEARANCE.accent,
    fontScale:
      typeof data.fontScale === "number" && Number.isFinite(data.fontScale)
        ? Math.min(1.2, Math.max(0.9, data.fontScale))
        : 1,
    density: data.density === "compact" ? "compact" : "comfortable",
    radius:
      typeof data.radius === "number" && Number.isFinite(data.radius)
        ? Math.min(20, Math.max(4, data.radius))
        : 12,
    heading: data.heading === "serif" ? "serif" : "sans",
  };
}

export function readAppearance(search = ""): Appearance {
  const params = new URLSearchParams(search);
  if (params.get("designPreview") === "1") {
    try {
      return normalizeAppearance(
        JSON.parse(params.get("designSettings") || "{}"),
      );
    } catch {
      return { ...DEFAULT_APPEARANCE };
    }
  }
  if (params.get("appearance") === "baseline")
    return { ...DEFAULT_APPEARANCE, preset: "baseline" };
  try {
    return normalizeAppearance(
      JSON.parse(localStorage.getItem(APPEARANCE_KEY) || "{}"),
    );
  } catch {
    return { ...DEFAULT_APPEARANCE };
  }
}

export function saveAppearance(value: Appearance) {
  const next = normalizeAppearance(value);
  localStorage.setItem(APPEARANCE_KEY, JSON.stringify(next));
  window.dispatchEvent(new CustomEvent(APPEARANCE_EVENT, { detail: next }));
}

function luminance(hex: string) {
  const channels = hex
    .slice(1)
    .match(/.{2}/g)!
    .map((part) => parseInt(part, 16) / 255)
    .map((x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}
export function appearanceStyle(value: Appearance): CSSProperties {
  const accent = luminance(value.accent);
  const whiteContrast = 1.05 / (accent + 0.05);
  const darkContrast = (accent + 0.05) / 0.05;
  const paper = luminance(
    value.preset === "workspace"
      ? "#F6F6F7"
      : value.preset === "stone"
        ? "#F5F6F3"
        : "#F8F6F0",
  );
  const linkContrast =
    (Math.max(paper, accent) + 0.05) / (Math.min(paper, accent) + 0.05);
  return {
    "--design-accent": value.accent,
    "--design-accent-text":
      whiteContrast >= darkContrast ? "#ffffff" : "#111111",
    "--design-accent-ink": linkContrast >= 4.5 ? value.accent : "#302D27",
    "--design-font": `${(value.preset === "workspace" ? 15 : 14) * value.fontScale}px`,
    "--design-gap":
      value.preset === "workspace"
        ? value.density === "compact"
          ? "16px"
          : "24px"
        : value.density === "compact"
          ? "18px"
          : "28px",
    "--design-radius": `${value.radius}px`,
    "--design-heading":
      value.heading === "serif"
        ? '"Palatino Linotype", "Book Antiqua", Batang, serif'
        : '"Klink Sans", Pretendard, "Malgun Gothic", sans-serif',
  } as CSSProperties;
}

export function HrAppearance({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [appearance, setAppearance] = useState(() =>
    readAppearance(location.search),
  );
  const [preview] = useState(
    () => new URLSearchParams(location.search).get("designPreview") === "1",
  );
  useEffect(() => {
    if (
      !preview ||
      new URLSearchParams(location.search).get("designPreview") === "1"
    )
      setAppearance(readAppearance(location.search));
  }, [location.search, preview]);
  useEffect(() => {
    const stored = () => {
      if (!preview) setAppearance(readAppearance(location.search));
    };
    const message = (event: MessageEvent) => {
      if (
        preview &&
        window.parent !== window &&
        event.origin === window.location.origin &&
        event.source === window.parent &&
        event.data?.type === "klink:appearance-preview"
      ) {
        setAppearance(normalizeAppearance(event.data.settings));
      }
    };
    window.addEventListener("storage", stored);
    window.addEventListener(APPEARANCE_EVENT, stored);
    window.addEventListener("message", message);
    if (preview && window.parent !== window)
      window.parent.postMessage(
        { type: "klink:appearance-ready" },
        window.location.origin,
      );
    return () => {
      window.removeEventListener("storage", stored);
      window.removeEventListener(APPEARANCE_EVENT, stored);
      window.removeEventListener("message", message);
    };
  }, [location.search, preview]);
  const archived = /(?:-previous|home-benchmark|wireframes)$/.test(
    location.pathname,
  );
  return (
    <div
      className="hr-appearance"
      data-hr-preset={archived ? "baseline" : appearance.preset}
      data-density={appearance.density}
      data-design-preview={preview}
      style={appearanceStyle(appearance)}
    >
      {children}
    </div>
  );
}
