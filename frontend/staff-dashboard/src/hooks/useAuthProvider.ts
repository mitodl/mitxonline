import { AuthProvider } from "@refinedev/core";
import axios from "axios";

export const PROFILE_KEY = "mitx-online-staff-profile";

// A full-page navigation to MITx Online's logout view.
export const logOutOfMitxOnline = () => {
  localStorage.removeItem(PROFILE_KEY);
  window.location.href = (new URL(DATASOURCES_CONFIG.mitxOnline)).origin + "/logout/";
};

export function useAuthProvider(): AuthProvider {
  const http = axios.create({
    baseURL: DATASOURCES_CONFIG.mitxOnline
  });
  const _ = require("lodash");

  return {
    // Sign-in happens on MITx Online itself (see pages/login.tsx), so there
    // is nothing to submit here.
    login: async () => {
      return { success: false, redirectTo: "/login" };
    },
    logout: async () => {
      logOutOfMitxOnline();
      return { success: true };
    },
    onError: async () => {
      return {};
    },
    check: async () => {
      let profile;
      try {
        profile = await http.get('v0/users/me');
      } catch (error) {
        localStorage.removeItem(PROFILE_KEY);
        return { authenticated: false, redirectTo: "/login", error: error as Error };
      }

      if (
        _.get(profile, "data.is_superuser") === true ||
        _.get(profile, "data.is_staff") === true
      ) {
        localStorage.setItem(PROFILE_KEY, JSON.stringify(profile.data));
        return { authenticated: true };
      }

      localStorage.removeItem(PROFILE_KEY);
      return { authenticated: false, redirectTo: "/login" };
    },
    getPermissions: async () => {
      /*
      For MITx Online currently, the only permissions we care about are the
      'is_staff' and 'is_superuser' flags.

      Future enhancement: The current profile API returns a list of all user
      permissions (as in, from the default Django permissions code), so the app
      could use this to determine permissions outside of those two flags. (This
      data is visible here.)
      */
      let profile = localStorage.getItem(PROFILE_KEY);

      if (profile) {
        profile = JSON.parse(profile);

        if (_.get(profile, "is_superuser")) {
          return ["superuser"];
        }

        if (_.get(profile, "is_staff")) {
          return ["staff"];
        }
      }

      return [];
    },
    getIdentity: async () => {
      const profile = localStorage.getItem(PROFILE_KEY);
      return profile ? JSON.parse(profile) : null;
    },
  };
};
