import React, { useState } from "react";

import { CanAccess, useGo, useMenu } from "@refinedev/core";

import { RightOutlined, LogoutOutlined } from "@ant-design/icons";

import { Layout as AntdLayout, Menu, Grid, Typography, Space, Divider } from "antd";
import { logOutOfMitxOnline } from "hooks/useAuthProvider";
import { Title } from "../title";
import { antLayoutSider, antLayoutSiderMobile } from "./styles";

export const Sider: React.FC = () => {
  const [collapsed, setCollapsed] = useState<boolean>(false);

  const { menuItems, selectedKey } = useMenu();
  const go = useGo();
  const breakpoint = Grid.useBreakpoint();

  const isMobile = !breakpoint.lg;

  return (
    <AntdLayout.Sider
      collapsible
      collapsed={collapsed}
      onCollapse={(collapsed: boolean): void => setCollapsed(collapsed)}
      collapsedWidth={isMobile ? 0 : 80}
      breakpoint="lg"
      style={isMobile ? antLayoutSiderMobile : antLayoutSider}
      theme="light"
    >
      <Title collapsed={collapsed} />
      <Space/>
      <Menu
        selectedKeys={[selectedKey]}
        mode="inline"
        onClick={({ key }) => {
          if (key === "logout") {
            // Not useLogout: it re-runs the auth check, whose redirect to
            // /login would race this full-page navigation.
            logOutOfMitxOnline();
            return;
          }

          if (!breakpoint.lg) {
            setCollapsed(true);
          }

          const item = menuItems.find((menuItem) => menuItem.key === key);
          if (item?.route) {
            go({ to: item.route });
          }
        }}
      >
        {menuItems.map(({ icon, label, key, name }) => {
          const isSelected = key === selectedKey;
          return (
            <CanAccess
              key={key}
              resource={name.toLowerCase()}
              action="list"
              >
              <Menu.Item
                style={{
                  fontWeight: isSelected ? "bold" : "normal",
                }}
                key={key}
                icon={icon}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  {label}
                  {!collapsed && isSelected && <RightOutlined />}
                </div>
              </Menu.Item>
            </CanAccess>
          );
        })}

        <Divider />

        <Menu.Item key="logout" icon={<LogoutOutlined />}>
          Logout
        </Menu.Item>
      </Menu>
    </AntdLayout.Sider>
  );
};
