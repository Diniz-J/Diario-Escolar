import { useContext } from "react";

import { PortalAuthContext } from "./PortalAuthContext";

export function usePortalAuth() {
  const ctx = useContext(PortalAuthContext);
  if (ctx == null) {
    throw new Error("usePortalAuth precisa estar dentro de PortalAuthProvider.");
  }
  return ctx;
}
