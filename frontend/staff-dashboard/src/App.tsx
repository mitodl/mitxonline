import { Refine } from "@pankod/refine-core";
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
import { DiscountList, DiscountEdit, DiscountShow, DiscountCreate } from "pages/discounts";
import { FlexiblePricingList } from "./pages/flexible_pricing";
import axios from "axios";
import useDrfDataProvider from "hooks/useDrfDataProvider";

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


const { RouterComponent : RefineRouterComponent } = routerProvider;

const RouterComponent = () => <RefineRouterComponent basename="/staff-dashboard" />;

export default function App() {
  const dataURI = DATASOURCES_CONFIG?.mitxOnline ?? "";
  const authProvider = useAuthProvider();
  const xonlineProvider = useDrfDataProvider(dataURI);

  return (
    <Refine
      routerProvider={{
        ...routerProvider,
        RouterComponent,
      }}
      notificationProvider={notificationProvider}
      dataProvider={xonlineProvider}
      authProvider={authProvider}
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