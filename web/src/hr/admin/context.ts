import { createContext, useContext } from "react";
import type { OpsSession } from "../operations";

export const AdminContext = createContext<OpsSession | null>(null);
export function useAdmin() {
  const value = useContext(AdminContext);
  if (!value) throw new Error("관리자 접속이 필요합니다.");
  return value;
}
