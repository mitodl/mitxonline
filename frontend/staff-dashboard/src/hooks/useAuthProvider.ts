import { AuthProvider } from "@pankod/refine-core";
import {useAuth, hasAuthParams} from "react-oidc-context";
import { User } from "oidc-client-ts";

export function useAuthProvider(): AuthProvider {
  const auth = useAuth()
  return {
    login: async () => {
      if (!hasAuthParams() &&
        !auth.isAuthenticated && !auth.activeNavigator && !auth.isLoading) {
        await auth.signinPopup()
        return Promise.resolve();
      }
    },
    logout: async () => {
      await auth.removeUser();
      return Promise.resolve();
    },
    checkError: async () => {
      return Promise.resolve();
    },
    checkAuth: async () => {
      let _ = require("lodash");
      if (auth.isAuthenticated && auth.user && _.get(auth.user, "profile.is_staff")) {
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
