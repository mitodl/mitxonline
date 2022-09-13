import { AuthProvider } from "@pankod/refine-core";
import { useAuth, hasAuthParams } from "react-oidc-context";
import { User } from "oidc-client-ts";

export function useAuthProvider(): AuthProvider {
  const auth = useAuth()
  return {
    login: async () => {
      if (!hasAuthParams() &&
        !auth.isAuthenticated && !auth.activeNavigator && !auth.isLoading) {
        let result = await auth.signinPopup()
        if (result && result.profile["is_staff"] === true) {
          return Promise.resolve();
        }
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
      let _ = require("lodash");
      if (auth.isAuthenticated && auth.user && _.get(auth.user, "profile.is_staff") === true) {
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
