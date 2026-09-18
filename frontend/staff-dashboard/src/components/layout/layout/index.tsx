import React from "react";

import { Layout as AntdLayout, Grid } from "antd";

import { Footer } from "../footer";
import { Header } from "../header";
import { OffLayoutArea } from "../offLayoutArea";
import { Sider } from "../sider";

export const Layout: React.FC<React.PropsWithChildren<{}>> = ({ children }) => {
  const breakpoint = Grid.useBreakpoint();
  return (
    <AntdLayout style={{ minHeight: "100vh", flexDirection: "row" }}>
      <Sider />
      <AntdLayout>
        <Header />
        <AntdLayout.Content>
          <div
            style={{
              padding: breakpoint.sm ? 24 : 12,
              minHeight: 360,
            }}
          >
            {children}
          </div>
          <OffLayoutArea />
        </AntdLayout.Content>
        <Footer />
      </AntdLayout>
    </AntdLayout>
  );
};
