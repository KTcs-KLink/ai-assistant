import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  Catalog,
  Configuration,
  EmployeeProfile,
  HR,
  HrError,
  HrSession,
  OfficialForm,
  Preparation,
  Readiness,
  ROOT,
  Updates,
  checkedCatalog,
  request,
} from "./api";

interface Data {
  session: HrSession | null;
  config: Configuration | null;
  catalog: Catalog | null;
  profile: EmployeeProfile | null;
  forms: OfficialForm[] | null;
  plans: Preparation[] | null;
  readiness: Readiness | null;
  updates: Updates | null;
}
interface HrState extends Data {
  state: "loading" | "offline" | "signedOut" | "connected";
  busy: boolean;
  notice: string;
  errors: string[];
  announce: (text: string) => void;
  refresh: () => Promise<void>;
  startDemo: () => Promise<void>;
  logout: () => Promise<void>;
  saveProfile: (profile: EmployeeProfile) => Promise<void>;
  revoke: () => Promise<void>;
  prepare: (benefit: Catalog["cards"][number]) => Promise<void>;
  check: (plan: Preparation, index: number, value: boolean) => Promise<void>;
  remove: (id: string) => Promise<void>;
  reminders: (enabled: boolean) => Promise<void>;
}
const EMPTY: Data = {
  session: null,
  config: null,
  catalog: null,
  profile: null,
  forms: null,
  plans: null,
  readiness: null,
  updates: null,
};
const Context = createContext<HrState | null>(null);
export function HrProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<Data>(EMPTY);
  const [state, setState] = useState<HrState["state"]>("loading");
  const [busy, setBusy] = useState(false),
    [notice, announce] = useState(""),
    [errors, setErrors] = useState<string[]>([]);
  const generation = useRef(0),
    lock = useRef(false);
  const handleError = useCallback((error: unknown) => {
    if (error instanceof HrError && error.status === 401) {
      generation.current++;
      setData((previous) => ({ ...EMPTY, config: previous.config }));
      setState("signedOut");
      announce("접속이 만료됐어요. 다시 시작해 주세요.");
      return;
    }
    announce(
      error instanceof Error ? error.message : "요청을 완료하지 못했어요.",
    );
  }, []);
  const load = useCallback(
    async (session: HrSession, config: Configuration | null, id: number) => {
      const results = await Promise.allSettled([
        request<Catalog>(HR + "/catalog").then(checkedCatalog),
        request<EmployeeProfile>(ROOT + "/profile"),
        request<{ forms: OfficialForm[] }>(HR + "/forms"),
        request<{ plans: Preparation[] }>(HR + "/preparations"),
        request<Readiness>(HR + "/readiness"),
        request<Updates>(HR + "/updates"),
      ]);
      if (id !== generation.current) return;
      const denied = results.find(
        (result) =>
          result.status === "rejected" &&
          result.reason instanceof HrError &&
          result.reason.status === 401,
      );
      if (denied?.status === "rejected") {
        handleError(denied.reason);
        return;
      }
      const value = <T,>(index: number): T | null =>
        results[index].status === "fulfilled"
          ? (results[index].value as T)
          : null;
      setData({
        session,
        config,
        catalog: value<Catalog>(0),
        profile: value<EmployeeProfile>(1),
        forms: value<{ forms: OfficialForm[] }>(2)?.forms ?? null,
        plans: value<{ plans: Preparation[] }>(3)?.plans ?? null,
        readiness: value<Readiness>(4),
        updates: value<Updates>(5),
      });
      const names = [
        "혜택 추천",
        "내 조건",
        "공식 양식",
        "준비 목록",
        "연결 상태",
        "변경 안내",
      ];
      setErrors(
        results.flatMap((result, index) =>
          result.status === "rejected"
            ? [
                names[index] +
                  ": " +
                  (result.reason instanceof Error
                    ? result.reason.message
                    : "조회하지 못했어요."),
              ]
            : [],
        ),
      );
      setState("connected");
    },
    [handleError],
  );
  const refresh = useCallback(async () => {
    const id = ++generation.current;
    try {
      const capability = await request<{ app: string }>(HR + "/capabilities");
      if (capability.app !== "KLINK_HR_DOMAIN")
        throw new HrError(
          0,
          "지정된 인사 서비스가 아닙니다. 연결 주소를 확인해 주세요.",
        );
      // Cloud ingestion is on hold. /config probes the external account store,
      // so local HR use does not request it or imply that storage was rechecked.
      const config: Configuration | null = null;
      if (id !== generation.current) return;
      try {
        const session = await request<HrSession>(ROOT + "/session");
        if (id === generation.current) await load(session, config, id);
      } catch (error) {
        if (id !== generation.current) return;
        if (error instanceof HrError && error.status === 401) {
          setData({ ...EMPTY, config });
          setErrors([]);
          setState("signedOut");
        } else throw error;
      }
    } catch (error) {
      if (id === generation.current) {
        setData(EMPTY);
        setState("offline");
        setErrors([
          error instanceof Error ? error.message : "연결을 확인하지 못했어요.",
        ]);
      }
    }
  }, [load]);
  useEffect(() => {
    void refresh();
    return () => {
      generation.current++;
    };
  }, [refresh]);
  const action = useCallback(
    async (run: () => Promise<void>) => {
      if (lock.current) return;
      lock.current = true;
      setBusy(true);
      announce("");
      try {
        await run();
      } catch (error) {
        handleError(error);
        throw error;
      } finally {
        lock.current = false;
        setBusy(false);
      }
    },
    [handleError],
  );
  async function reload() {
    const id = ++generation.current;
    if (data.session) await load(data.session, data.config, id);
  }
  const value: HrState = {
    ...data,
    state,
    busy,
    notice,
    errors,
    announce,
    refresh,
    startDemo: () =>
      action(async () => {
        const id = ++generation.current;
        const session = await request<HrSession>(
          ROOT + "/session/demo",
          "POST",
        );
        await request(ROOT + "/profile/example", "POST");
        await load(session, data.config, id);
        announce(
          "서버의 예시 직원 조건을 불러왔어요. 실제 회사 계정은 아닙니다.",
        );
      }),
    logout: () =>
      action(async () => {
        await request(ROOT + "/session", "DELETE");
        generation.current++;
        setData((previous) => ({ ...EMPTY, config: previous.config }));
        setErrors([]);
        setState("signedOut");
        announce("서버에서 접속을 종료했어요.");
      }),
    saveProfile: (profile) =>
      action(async () => {
        await request(ROOT + "/profile", "PUT", profile);
        await reload();
        announce(
          "서버에 조건을 반영했어요. 이전 준비 항목은 다시 확인해 주세요.",
        );
      }),
    revoke: () =>
      action(async () => {
        await request(ROOT + "/profile", "DELETE");
        await reload();
        announce("서버에서 동의를 철회하고 조건·준비·알림 정보를 비웠어요.");
      }),
    prepare: (benefit) =>
      action(async () => {
        if (!data.catalog)
          throw new HrError(0, "최신 혜택을 먼저 확인해 주세요.");
        try {
          await request(
            HR + "/preparations/" + encodeURIComponent(benefit.id),
            "POST",
            {
              conditions_revision: data.catalog.conditions_revision,
              policy_sha256: benefit.policy_sha256,
            },
          );
        } catch (error) {
          if (error instanceof HrError && error.status === 409) await reload();
          throw error;
        }
        await reload();
        announce("서버 준비 목록에 담았어요. 실제 신청은 제출되지 않았습니다.");
      }),
    check: (plan, index, checked) =>
      action(async () => {
        try {
          await request(
            HR + "/preparations/" + encodeURIComponent(plan.id),
            "PATCH",
            { index, checked },
          );
        } catch (error) {
          if (error instanceof HrError && error.status === 409) await reload();
          throw error;
        }
        await reload();
      }),
    remove: (id) =>
      action(async () => {
        await request(HR + "/preparations/" + encodeURIComponent(id), "DELETE");
        await reload();
        announce("서버 준비 목록에서 삭제했어요.");
      }),
    reminders: (enabled) =>
      action(async () => {
        await request(HR + "/reminders", "PUT", { enabled });
        await reload();
        announce(
          enabled
            ? "화면 안의 변경·마감 안내를 켰어요. 외부 알림은 발송하지 않습니다."
            : "변경·마감 안내를 껐어요.",
        );
      }),
  };
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useHr() {
  const value = useContext(Context);
  if (!value) throw new Error("HrProvider required");
  return value;
}
