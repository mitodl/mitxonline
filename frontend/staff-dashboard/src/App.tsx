import { Refine, useGetIdentity } from "@pankod/refine-core";
import { Icons, notificationProvider } from "@pankod/refine-antd";
import routerProvider from "@pankod/refine-react-router-v6";
import "@pankod/refine-antd/dist/styles.min.css";
import { useAuthProvider } from "hooks/useAuthProvider";
import {
  Title,
  Header,
  Sider,
  Footer,
  Layout,
  OffLayoutArea,
} from "components/layout";
import LoginPage from "pages/login";
import { DashboardPage } from "pages/dashboard";
import { DiscountList, DiscountEdit, DiscountShow, DiscountCreate, BulkDiscountCreate } from "pages/discounts";
import { FlexiblePricingList } from "./pages/flexible_pricing";
import axios from "axios";
import useDrfDataProvider from "hooks/useDrfDataProvider";
import { Routes, Route } from "react-router-dom";

import "styles/antd.less";

const {UserOutlined, BarcodeOutlined, FormOutlined} = Icons;
const axiosInterface = axios.create();

axiosInterface.interceptors.request.use((config: any) => {
  let token = sessionStorage.getItem(`oidc.user:${OIDC_CONFIG.authority}:${OIDC_CONFIG.client_id}`);

  if (token !== null) {
    token = JSON.parse(token).access_token;
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
}, (error: any) => Promise.reject(error));

const _ = require("lodash");

const { RouterComponent : RefineRouterComponent } = routerProvider;

const customRoutes = [
  {
    element: <BulkDiscountCreate />,
    path: "discounts/create_batch",
    layout: true,
  }
];

const RouterComponent = () => (<RefineRouterComponent basename="/staff-dashboard" />);

export default function App() {
  const dataURI = DATASOURCES_CONFIG?.mitxOnline ?? "";
  const authProvider = useAuthProvider();
  const xonlineProvider = useDrfDataProvider(dataURI);

  return (
    <Refine
      routerProvider={{
        ...routerProvider,
        RouterComponent,
        routes: customRoutes
      }}
      notificationProvider={notificationProvider}
      dataProvider={xonlineProvider}
      authProvider={authProvider}
      accessControlProvider={{
        can: async ({ action, params, resource }) => {
          let profile = localStorage.getItem("mitx-online-staff-profile");
          if (profile) {
            profile = JSON.parse(profile);
          } else {
            return Promise.resolve({ can: false, reason: "You don't have a valid session." });
          }

          if (_.get(profile, 'is_superuser')) {
            return Promise.resolve({ can: true });
          }

          if (_.get(profile, 'is_staff')) {
            if (resource == 'dashboard' || resource == 'flexible_pricing') {
              return Promise.resolve({ can: true });
            }
          }

          return Promise.resolve({ can: false, reason: 'Your account is not allowed to do that.' });
        }
      }}
      LoginPage={LoginPage}
      DashboardPage={DashboardPage}
      resources={[
        // {
        //   name: "learners",
        //   icon: <UserOutlined/>
        // },
        {
          name: "discounts",
          icon: <BarcodeOutlined/>,
          show: DiscountShow,
          list: DiscountList,
          edit: DiscountEdit,
          create: DiscountCreate,
        },
        {
          name: 'flexible_pricing',
          icon: <FormOutlined/>,
          options: {
            label: 'Flexible Pricing'
          },
          list: FlexiblePricingList,
        }
      ]}
      Title={Title}
      Header={Header}
      Sider={Sider}
      Footer={Footer}
      Layout={Layout}
      OffLayoutArea={OffLayoutArea}
    />
  );
}
