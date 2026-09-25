import React from "react";
import { EditButton, RefreshButton, Show } from "@refinedev/antd";
import { useShow } from "@refinedev/core";
import { Card, Col, Descriptions, Row, Space, Tag, Typography } from "antd";

import { IdentityProviders } from "components/b2b/identity_providers";
import { OnboardingCard } from "components/b2b/onboarding_card";
import { ProvisioningEvents } from "components/b2b/provisioning_events";
import { IProvisionedOrganization } from "interfaces";

export const OrganizationShow: React.FC = () => {
    const { query } = useShow<IProvisionedOrganization>();
    const organization = query.data?.data;

    return (
        <Show
            isLoading={query.isLoading}
            title={organization?.name ?? "Organization"}
            headerButtons={({ refreshButtonProps }) => (
                <>
                    <RefreshButton {...refreshButtonProps} />
                    <EditButton recordItemId={organization?.org_key} />
                </>
            )}
        >
            {organization && (
                <Row gutter={[16, 16]}>
                    <Col xs={24} lg={14}>
                        <Card title="Organization">
                            <Descriptions column={1} size="small">
                                <Descriptions.Item label="Org key">
                                    <Typography.Text code>{organization.org_key}</Typography.Text>
                                </Descriptions.Item>
                                <Descriptions.Item label="Org key prefix">{organization.org_key_prefix || "none"}</Descriptions.Item>
                                <Descriptions.Item label="Email domains">
                                    {organization.domains === null ? (
                                        <Typography.Text type="secondary">Not read from Keycloak</Typography.Text>
                                    ) : organization.domains.length === 0 ? (
                                        "none"
                                    ) : (
                                        <Space wrap>
                                            {organization.domains.map((domain) => <Tag key={domain}>{domain}</Tag>)}
                                        </Space>
                                    )}
                                </Descriptions.Item>
                                <Descriptions.Item label="Post-login redirect">{organization.redirect_url || "none"}</Descriptions.Item>
                                <Descriptions.Item label="Keycloak organization">
                                    {organization.sso_organization_id ? (
                                        <Typography.Text code copyable>{organization.sso_organization_id}</Typography.Text>
                                    ) : (
                                        <Typography.Text type="danger">Not linked to Keycloak</Typography.Text>
                                    )}
                                </Descriptions.Item>
                                {organization.description && (
                                    <Descriptions.Item label="Description">{organization.description}</Descriptions.Item>
                                )}
                            </Descriptions>
                        </Card>
                    </Col>
                    <Col xs={24} lg={10}>
                        <OnboardingCard organization={organization} />
                    </Col>
                    <Col span={24}>
                        <IdentityProviders organization={organization} />
                    </Col>
                    <Col span={24}>
                        <ProvisioningEvents orgKey={organization.org_key} />
                    </Col>
                </Row>
            )}
        </Show>
    );
};
