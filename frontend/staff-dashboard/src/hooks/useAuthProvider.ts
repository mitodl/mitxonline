import { AuthProvider } from "@pankod/refine-core";
import {useAuth} from "react-oidc-context";

export function useAuthProvider(): AuthProvider {
  const auth = useAuth()
  return {
    login: async () => {
      await auth.signinPopup();
      return Promise.resolve();
    },
    logout: async () => {
      await auth.removeUser();
      return Promise.resolve();
    },
    checkError: async () => Promise.resolve(),
    checkAuth: async () => {
      if (auth.isAuthenticated) {
        return Promise.resolve();
      }
      return Promise.reject()
    },
    getPermissions: () => Promise.resolve(),
    getUserIdentity: async () => {
      return auth.user ? Promise.resolve(auth.user) : Promise.reject()
    },
  };
};
