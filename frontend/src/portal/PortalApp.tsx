import { PortalAuthProvider } from "@/features/portal/PortalAuthContext";

import { PortalRoutes } from "./PortalRoutes";

/** Raiz do portal do responsável. Chunk separado do staff. */
export default function PortalApp() {
  return (
    <PortalAuthProvider>
      <PortalRoutes />
    </PortalAuthProvider>
  );
}
