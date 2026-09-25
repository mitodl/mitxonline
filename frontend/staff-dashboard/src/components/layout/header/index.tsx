import React from "react";
import { useGetIdentity } from "@refinedev/core";
import { Layout as AntdLayout, Typography, Avatar, Space } from "antd";

const { Text } = Typography;

export const Header: React.FC = () => {
  const { data: user } = useGetIdentity({
    v3LegacyAuthProviderCompatible: true
  });

  const shouldRenderHeader = user && (user.name || user.avatar);

  return shouldRenderHeader ? (
    <AntdLayout.Header
      style={{
        display: "flex",
        justifyContent: "flex-end",
        alignItems: "center",
        padding: "0px 24px",
        height: "64px",
        backgroundColor: "#FFF",
      }}
    >
      <Space>
        {user.name && (
          <Text ellipsis strong>
            {user.name}
          </Text>
        )}
        {user.avatar && (
          <Avatar size="large" src={user?.avatar} alt={user?.name} />
        )}
      </Space>
    </AntdLayout.Header>
  ) : null;
};
