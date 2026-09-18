import { Authenticated, CanAccess, Refine } from "@refinedev/core";
import { ErrorComponent, useNotificationProvider } from "@refinedev/antd";
import routerProvider, { CatchAllNavigate } from "@refinedev/react-router-v6";
import { App as AntdApp } from "antd";
import { BarcodeOutlined, FormOutlined } from "@ant-design/icons";
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom";

import "@refinedev/antd/dist/reset.css";
import { PROFILE_KEY, useAuthProvider } from "hooks/useAuthProvider";
import { Layout } from "components/layout";
import LoginPage from "pages/login";
import { DashboardPage } from "pages/dashboard";
import { DiscountList, DiscountEdit, DiscountShow, DiscountCreate, BulkDiscountCreate } from "pages/discounts";
import { FlexiblePricingList } from "./pages/flexible_pricing";
import useDrfDataProvider from "hooks/useDrfDataProvider";

import "styles/antd.less";

const _ = require("lodash");

const accessControlProvider = {
  can: async ({ resource }: { resource?: string }) => {
    let profile = localStorage.getItem(PROFILE_KEY);
    if (profile) {
      profile = JSON.parse(profile);
    } else {
      return { can: false, reason: "You don't have a valid session." };
    }

    if (_.get(profile, 'is_superuser')) {
      return { can: true };
    }

    if (_.get(profile, 'is_staff')) {
      if (resource == 'flexible_pricing') {
        return { can: true };
      }
    }

    return { can: false, reason: 'Your account is not allowed to do that.' };
  }
};

export default function App() {
  const dataURI = DATASOURCES_CONFIG?.mitxOnline ?? "";
  const authProvider = useAuthProvider();
  const xonlineProvider = useDrfDataProvider(dataURI);

  return (
    <BrowserRouter basename="/staff-dashboard">
      <AntdApp>
        <Refine
          routerProvider={routerProvider}
          notificationProvider={useNotificationProvider}
          dataProvider={xonlineProvider}
          authProvider={authProvider}
          accessControlProvider={accessControlProvider}
          resources={[
            {
              name: "discounts",
              list: "/discounts",
              show: "/discounts/show/:id",
              edit: "/discounts/edit/:id",
              create: "/discounts/create",
              meta: {
                icon: <BarcodeOutlined/>,
              },
            },
            {
              name: 'flexible_pricing',
              list: "/flexible_pricing",
              meta: {
                label: 'Flexible Pricing',
                icon: <FormOutlined/>,
              },
            }
          ]}
        >
          <Routes>
            <Route
              element={
                <Authenticated key="authenticated" fallback={<CatchAllNavigate to="/login" />}>
                  <Layout>
                    <Outlet />
                  </Layout>
                </Authenticated>
              }
            >
              <Route index element={<DashboardPage />} />
              <Route element={<CanAccess fallback={<ErrorComponent />}><Outlet /></CanAccess>}>
                <Route path="/discounts">
                  <Route index element={<DiscountList />} />
                  <Route path="create" element={<DiscountCreate />} />
                  <Route path="create_batch" element={<BulkDiscountCreate />} />
                  <Route path="show/:id" element={<DiscountShow />} />
                  <Route path="edit/:id" element={<DiscountEdit />} />
                </Route>
                <Route path="/flexible_pricing" element={<FlexiblePricingList />} />
              </Route>
              <Route path="*" element={<ErrorComponent />} />
            </Route>
            <Route path="/login" element={<LoginPage />} />
          </Routes>
        </Refine>
      </AntdApp>
    </BrowserRouter>
  );
}
