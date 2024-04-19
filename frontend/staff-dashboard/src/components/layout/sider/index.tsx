import React, { useState } from "react";

import { CanAccess, useLogout, useTitle, useNavigation } from "@pankod/refine-core";
import { AntdLayout, Menu, Grid, Icons, useMenu, Typography, Space, Divider } from "@pankod/refine-antd";
import { antLayoutSider, antLayoutSiderMobile } from "./styles";

const { RightOutlined, LogoutOutlined } = Icons;

export const Sider: React.FC = () => {
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const { mutate: logout } = useLogout();
  const Title = useTitle();
  const { menuItems, selectedKey } = useMenu();
  const { push } = useNavigation();
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
      {Title && <Title collapsed={collapsed} />}
      <Space/>
      <Menu
        selectedKeys={[selectedKey]}
        mode="inline"
        onClick={({ key }) => {
          if (key === "logout") {
            localStorage.removeItem("mitx-online-staff-profile");
            const logoutPath = (new URL(DATASOURCES_CONFIG.mitxOnline)).origin + "/logout/";
            window.location.href = logoutPath;

            return;
          }

          if (!breakpoint.lg) {
            setCollapsed(true);
          }

          push(key as string);
        }}
      >
        {menuItems.map(({ icon, label, route, name }) => {
          const isSelected = route === selectedKey;
          return (
            <CanAccess
              key={route}
              resource={name.toLowerCase()}
              action="list"
              >
              <Menu.Item
                style={{
                  fontWeight: isSelected ? "bold" : "normal",
                }}
                key={route}
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
