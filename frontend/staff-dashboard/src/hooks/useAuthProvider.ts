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
      } else if (auth && auth.user && auth.user.profile.is_staff === true) {
        return Promise.resolve();
      }
      return Promise.reject();
    },
    logout: async () => {
      await auth.removeUser();
      return Promise.resolve();
    },
    checkError: async () => {
      return Promise.resolve();
    },
    checkAuth: async () => {
      let token = sessionStorage.getItem(`oidc.user:${OIDC_CONFIG.authority}:${OIDC_CONFIG.client_id}`);
      if (!auth.isLoading && !auth.isAuthenticated && token) {
        console.log("here")
        let result = await auth.signinSilent();
        return Promise.resolve();
      }
    },
    getPermissions: () => Promise.resolve(),
    getUserIdentity: async () => {
      return auth.user ? Promise.resolve(auth.user) : Promise.reject()
    },
  };
};
