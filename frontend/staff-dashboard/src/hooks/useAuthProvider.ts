import { AuthProvider } from "@pankod/refine-core";
import axios from "axios";

export function useAuthProvider(): AuthProvider {
  const http = axios.create({
    baseURL: DATASOURCES_CONFIG.mitxOnline
  });
  const _ = require("lodash");

  const getProfile = async () => {
    const profile = await http.get('users/me');

    return Promise.resolve(profile.data);
  }

  return {
    login: async () => {
      const profile = await getProfile();

      if (_.get(profile, "data.is_staff") === true) {
        localStorage.setItem('mitx-online-staff-profile', JSON.stringify(profile.data));
        return Promise.resolve();
      }

      localStorage.removeItem("mitx-online-staff-profile");

      return Promise.reject({
        name: "Not Authenticated",
        message: "Your account doesn't have permission to view this page."
      });
    },
    logout: async () => {
      localStorage.removeItem("mitx-online-staff-profile");
      const logoutPath = (new URL(DATASOURCES_CONFIG.mitxOnline)).origin + "/logout/";
      window.location.href = logoutPath;
      return Promise.resolve();
    },
    checkError: async () => {
      return Promise.resolve();
    },
    checkAuth: async () => {
      const profile = await http.get('users/me');

      if (
        _.get(profile, "data.is_superuser") === true ||
        _.get(profile, "data.is_staff") === true
      ) {
        localStorage.setItem('mitx-online-staff-profile', JSON.stringify(profile.data));
        return Promise.resolve();
      }
      return Promise.reject({
        redirectPath: (new URL(DATASOURCES_CONFIG.mitxOnline)).origin + "/signin"
      });
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
      let profile = localStorage.getItem("mitx-online-staff-profile");

      if (profile) {
        profile = JSON.parse(profile);

        if (_.get(profile, "is_superuser")) {
          return Promise.resolve(["superuser"]);
        }

        if (_.get(profile, "is_staff")) {
          return Promise.resolve(["staff"]);
        }
      }

      return Promise.resolve([]);
    },
    getUserIdentity: async () => {
      let profile = localStorage.getItem("mitx-online-staff-profile");
      return profile ? Promise.resolve(JSON.parse(profile)) : Promise.reject()
    },
  };
};
