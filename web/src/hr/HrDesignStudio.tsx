import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  ArrowUpRight,
  Check,
  ChevronDown,
  CircleHelp,
  Columns2,
  Download,
  Maximize2,
  Monitor,
  Palette,
  RotateCcw,
  SlidersHorizontal,
  Smartphone,
} from "lucide-react";
import {
  DEFAULT_APPEARANCE,
  PRESETS,
  normalizeAppearance,
  readAppearance,
  saveAppearance,
  type Appearance,
} from "./appearance";
import "./design-studio.css";

const SCREENS = [
  { path: "/hr", label: "직원 · 업무 홈", group: "직원 화면" },
  { path: "/hr/assistant", label: "직원 · AI 도우미", group: "직원 화면" },
  { path: "/hr/library", label: "직원 · 규정·양식", group: "직원 화면" },
  { path: "/hr/requests", label: "직원 · 내 문의", group: "직원 화면" },
  { path: "/hr/profile", label: "직원 · 내 계정", group: "직원 화면" },
  { path: "/hr/admin", label: "관리자 · 운영 현황", group: "관리자 화면" },
  {
    path: "/hr/admin/sources",
    label: "관리자 · 원문·데이터",
    group: "관리자 화면",
  },
  {
    path: "/hr/admin/jobs",
    label: "관리자 · 수집·재적재",
    group: "관리자 화면",
  },
  {
    path: "/hr/admin/usage",
    label: "관리자 · 토큰·비용",
    group: "관리자 화면",
  },
  {
    path: "/hr/admin/settings",
    label: "관리자 · 예산·권한",
    group: "관리자 화면",
  },
] as const;
const SWATCHES = [
  { name: "테라코타", hex: "#A65035" },
  { name: "세이지", hex: "#3D6255" },
  { name: "차콜", hex: "#44423D" },
  { name: "딥 블루", hex: "#365D85" },
];

export default function HrDesignStudio() {
  const [draft, setDraft] = useState<Appearance>(() => readAppearance());
  const [path, setPath] = useState<string>("/hr");
  const [device, setDevice] = useState<"desktop" | "mobile">("desktop");
  const [compare, setCompare] = useState(false);
  const [width, setWidth] = useState(900);
  const [notice, setNotice] = useState("");
  const frame = useRef<HTMLIFrameElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const shown = compare ? { ...draft, preset: "baseline" as const } : draft;
  const shownRef = useRef(shown);
  useEffect(() => {
    shownRef.current = compare ? { ...draft, preset: "baseline" } : draft;
  });
  const send = useCallback(() => {
    frame.current?.contentWindow?.postMessage(
      { type: "klink:appearance-preview", settings: shownRef.current },
      window.location.origin,
    );
  }, []);
  useEffect(() => {
    send();
  }, [draft, compare, send]);
  useEffect(() => {
    document.title = "K:LINK · 디자인 스튜디오";
    const observer = new ResizeObserver((entries) =>
      setWidth(entries[0].contentRect.width),
    );
    if (stage.current) observer.observe(stage.current);
    const ready = (event: MessageEvent) => {
      if (
        event.origin === window.location.origin &&
        event.source === frame.current?.contentWindow &&
        event.data?.type === "klink:appearance-ready"
      )
        send();
    };
    window.addEventListener("message", ready);
    return () => {
      observer.disconnect();
      window.removeEventListener("message", ready);
    };
  }, [send]);
  const patch = (value: Partial<Appearance>) => {
    setDraft((old) =>
      normalizeAppearance({
        ...old,
        preset:
          old.preset === "baseline" && !value.preset ? "paper" : old.preset,
        ...value,
      }),
    );
    setCompare(false);
    setNotice("");
  };
  const apply = () => {
    try {
      saveAppearance(shownRef.current);
      setNotice(
        "이 브라우저의 직원·관리자 화면에 적용했습니다. 회사 공통 설정은 변경하지 않습니다.",
      );
    } catch {
      setNotice(
        "브라우저 저장이 차단되어 적용하지 못했습니다. 미리보기는 계속 사용할 수 있습니다.",
      );
    }
  };
  const download = () => {
    const blob = new Blob(
      [
        JSON.stringify(
          {
            product: "KLINK",
            kind: "appearance",
            version: 1,
            settings: shownRef.current,
          },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "klink-design.json";
    link.click();
    URL.revokeObjectURL(url);
    setNotice(
      "색상·글자·간격 설정을 내려받았습니다. 직원 정보나 업무 데이터는 포함하지 않습니다.",
    );
  };
  const deviceWidth = device === "desktop" ? 1280 : 390;
  const deviceHeight = device === "desktop" ? 900 : 844;
  const scale = Math.min(1, Math.max(0.2, (width - 48) / deviceWidth));
  // Keep the frame URL stable while controls change; postMessage preserves in-frame work.
  const [initial] = useState(() => JSON.stringify(readAppearance()));
  const frameUrl = `${path}?designPreview=1&designSettings=${encodeURIComponent(initial)}`;
  const openUrl = `${path}?designPreview=1&designSettings=${encodeURIComponent(JSON.stringify(shown))}`;
  return (
    <div className="ds-app">
      <header className="ds-header">
        <div>
          <Link
            className="ds-back"
            to="/hr"
            aria-label="직원 화면으로 돌아가기"
          >
            <ArrowLeft size={17} />
          </Link>
          <strong>K:LINK</strong>
          <span className="ds-header-divider" />
          <span>디자인 스튜디오</span>
          <i>LOCAL</i>
        </div>
        <div>
          <Link className="ds-wireframes" to="/hr/wireframes">
            화면 구성
          </Link>
          <button
            className="ds-export"
            onClick={download}
            aria-label="디자인 설정 내려받기"
          >
            <Download size={15} />
          </button>
          <button className="ds-apply" onClick={apply}>
            <Check size={15} />이 디자인 적용
          </button>
        </div>
      </header>
      <div className="ds-workbench">
        <main className="ds-canvas-area">
          <div className="ds-canvas-toolbar">
            <label className="ds-screen-picker">
              <span className="ds-visually-hidden">미리볼 화면</span>
              <select
                aria-label="미리볼 화면"
                value={path}
                onChange={(e) => {
                  setPath(e.target.value);
                  setNotice("");
                }}
              >
                {["직원 화면", "관리자 화면"].map((group) => (
                  <optgroup key={group} label={group}>
                    {SCREENS.filter((x) => x.group === group).map((x) => (
                      <option key={x.path} value={x.path}>
                        {x.label}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <ChevronDown size={14} />
            </label>
            <div className="ds-device-switch">
              <button
                aria-label="PC 미리보기"
                aria-pressed={device === "desktop"}
                onClick={() => setDevice("desktop")}
              >
                <Monitor size={16} />
              </button>
              <button
                aria-label="모바일 미리보기"
                aria-pressed={device === "mobile"}
                onClick={() => setDevice("mobile")}
              >
                <Smartphone size={16} />
              </button>
            </div>
            <div className="ds-view-actions">
              <button
                className={compare ? "is-active" : ""}
                aria-pressed={compare}
                onClick={() => setCompare((x) => !x)}
              >
                <Columns2 size={15} />
                기존 시안 비교
              </button>
              <a
                href={openUrl}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="선택한 디자인 크게 열기"
              >
                <Maximize2 size={15} />
              </a>
            </div>
          </div>
          <div className="ds-intro">
            <div>
              <span>DESIGN EXPLORATION</span>
              <h1>더 편안한 업무 공간.</h1>
            </div>
            <p>
              시안을 고르고, 오른쪽에서 다듬어 보세요.
              <br />
              실제 화면에 바로 반영해 비교합니다.
            </p>
          </div>
          <div className="ds-stage" ref={stage}>
            <div
              className={
                "ds-preview " + (device === "mobile" ? "is-mobile" : "")
              }
              style={{
                width: deviceWidth * scale,
                height: deviceHeight * scale,
              }}
            >
              <iframe
                ref={frame}
                src={frameUrl}
                onLoad={send}
                title="실제 KLINK 화면 디자인 미리보기"
                style={{
                  width: deviceWidth,
                  height: deviceHeight,
                  transform: `scale(${scale})`,
                }}
              />
            </div>
          </div>
          <div className="ds-canvas-foot">
            <span>
              <i />
              실제 화면 미리보기 ·{" "}
              {compare
                ? "보존된 기존 시안"
                : PRESETS.find((x) => x.id === draft.preset)?.name}
            </span>
            <span>
              {deviceWidth} × {deviceHeight} · {Math.round(scale * 100)}%
            </span>
          </div>
          {notice && (
            <div className="ds-notice" role="status">
              <Check size={16} />
              <p>{notice}</p>
            </div>
          )}
        </main>
        <aside className="ds-properties" aria-label="디자인 조절">
          <header>
            <SlidersHorizontal size={17} />
            <h2>디자인 조절</h2>
            <span>바로 미리보기</span>
          </header>
          <section className="ds-preset-section">
            <div className="ds-section-label">
              <Palette size={14} />
              스타일
            </div>
            <div className="ds-presets">
              {PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  className={
                    "ds-preset " +
                    (draft.preset === preset.id && !compare ? "selected" : "")
                  }
                  onClick={() =>
                    patch({
                      preset: preset.id,
                      accent: preset.accent,
                      heading: preset.id === "baseline" ? "sans" : "serif",
                    })
                  }
                  aria-pressed={draft.preset === preset.id && !compare}
                >
                  <div
                    className="ds-mini-preview"
                    style={{ background: preset.canvas }}
                  >
                    <i style={{ background: preset.side }} />
                    <div>
                      <b style={{ background: preset.accent }} />
                      <span />
                      <span />
                      <em />
                    </div>
                  </div>
                  <strong>
                    {preset.name}
                    {draft.preset === preset.id && !compare && (
                      <Check size={13} />
                    )}
                  </strong>
                  <small>{preset.description}</small>
                </button>
              ))}
            </div>
          </section>
          <section>
            <div className="ds-section-label">포인트 색상</div>
            <div className="ds-swatches">
              {SWATCHES.map((swatch) => (
                <button
                  key={swatch.hex}
                  aria-label={swatch.name + " 색상"}
                  aria-pressed={
                    draft.accent.toLowerCase() === swatch.hex.toLowerCase()
                  }
                  style={{ background: swatch.hex }}
                  onClick={() => patch({ accent: swatch.hex })}
                >
                  {draft.accent.toLowerCase() === swatch.hex.toLowerCase() && (
                    <Check size={15} />
                  )}
                </button>
              ))}
              <label className="ds-custom-color">
                <input
                  aria-label="사용자 지정 포인트 색상"
                  type="color"
                  value={draft.accent}
                  onChange={(e) => patch({ accent: e.target.value })}
                />
                <span>직접 선택</span>
              </label>
            </div>
            <p className="ds-help">
              버튼 글자색은 읽기 쉬운 대비로 조정합니다.
            </p>
          </section>
          <section>
            <div className="ds-section-label">글자</div>
            <label className="ds-range-label" htmlFor="design-font">
              <span>글자 크기</span>
              <output>{Math.round(draft.fontScale * 100)}%</output>
            </label>
            <input
              id="design-font"
              type="range"
              min="90"
              max="120"
              step="5"
              value={Math.round(draft.fontScale * 100)}
              onChange={(e) =>
                patch({ fontScale: Number(e.target.value) / 100 })
              }
            />
            <div className="ds-segment" aria-label="제목 서체">
              <button
                aria-pressed={draft.heading === "serif"}
                onClick={() => patch({ heading: "serif" })}
                style={{ fontFamily: "Georgia, Batang, serif" }}
              >
                편안한 제목
              </button>
              <button
                aria-pressed={draft.heading === "sans"}
                onClick={() => patch({ heading: "sans" })}
              >
                또렷한 제목
              </button>
            </div>
          </section>
          <section>
            <div className="ds-section-label">레이아웃</div>
            <label className="ds-range-label" htmlFor="design-radius">
              <span>모서리</span>
              <output>{draft.radius}px</output>
            </label>
            <input
              id="design-radius"
              type="range"
              min="4"
              max="20"
              step="2"
              value={draft.radius}
              onChange={(e) => patch({ radius: Number(e.target.value) })}
            />
            <div className="ds-density-label">정보 간격</div>
            <div className="ds-segment">
              <button
                aria-pressed={draft.density === "comfortable"}
                onClick={() => patch({ density: "comfortable" })}
              >
                여유롭게
              </button>
              <button
                aria-pressed={draft.density === "compact"}
                onClick={() => patch({ density: "compact" })}
              >
                촘촘하게
              </button>
            </div>
          </section>
          <footer>
            <button
              className="ds-reset"
              onClick={() => {
                setDraft({ ...DEFAULT_APPEARANCE });
                setCompare(false);
                setNotice(
                  "페이퍼 기본 디자인으로 되돌렸습니다. 적용 전에는 미리보기만 바뀝니다.",
                );
              }}
            >
              <RotateCcw size={14} />
              기본 디자인으로
            </button>
            <div>
              <CircleHelp size={14} />
              <p>
                색상·배치만 바꿉니다. AI·원문 연결과 업무 데이터는 그대로
                사용하며, 회사 적용 상태도 유지합니다.
              </p>
            </div>
            <a href={openUrl} target="_blank" rel="noopener noreferrer">
              선택한 화면 크게 보기
              <ArrowUpRight size={13} />
            </a>
          </footer>
        </aside>
      </div>
    </div>
  );
}
