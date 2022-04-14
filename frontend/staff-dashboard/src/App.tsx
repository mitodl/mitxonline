import { Refine } from "@pankod/refine-core";
import { Icons, notificationProvider } from "@pankod/refine-antd";
import routerProvider from "@pankod/refine-react-router-v6";
import "@pankod/refine-antd/dist/styles.min.css";
import dataProvider from "@pankod/refine-simple-rest";
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

const {UserOutlined} = Icons;

export default function App() {
  const authProvider = useAuthProvider();
  return (
    <Refine
      routerProvider={routerProvider}
      notificationProvider={notificationProvider}
      dataProvider={dataProvider("https://api.fake-rest.refine.dev")}
      authProvider={authProvider}
      LoginPage={LoginPage}
      DashboardPage={DashboardPage}
      resources={[{name: "learners", icon: <UserOutlined/>}]}
      Title={Title}
      Header={Header}
      Sider={Sider}
      Footer={Footer}
      Layout={Layout}
      OffLayoutArea={OffLayoutArea}
    />
  );
}