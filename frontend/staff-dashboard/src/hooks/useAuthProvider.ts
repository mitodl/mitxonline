import { AuthProvider } from "@pankod/refine-core";
import {useAuth, hasAuthParams} from "react-oidc-context";
import { User } from "oidc-client-ts";

export function useAuthProvider(): AuthProvider {
  const auth = useAuth()
  return {
    login: async () => {
      if (!hasAuthParams() &&
        !auth.isAuthenticated && !auth.activeNavigator && !auth.isLoading) {
        let result = await auth.signinPopup();
        if (result.profile.is_staff) {
          return Promise.resolve();
        }
      }
      return Promise.reject();
    },
    logout: async () => {
      sessionStorage.removeItem(`oidc.user:${OIDC_CONFIG.authority}:${OIDC_CONFIG.client_id}`);
      await auth.removeUser();
      return Promise.resolve();
    },
    checkError: async () => {
      return Promise.resolve();
    },
    checkAuth: async () => {
      if (auth.isAuthenticated) {
        return Promise.resolve();
      }
      return Promise.reject();
    },
    getPermissions: () => Promise.resolve(),
    getUserIdentity: async () => {
      return auth.user ? Promise.resolve(auth.user) : Promise.reject()
    },
  };
};
