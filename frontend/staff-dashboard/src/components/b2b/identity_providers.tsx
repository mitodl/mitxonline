import React from "react";
import { useApiUrl, useCustomMutation, useGo } from "@refinedev/core";
import { Button, Card, Descriptions, Dropdown, Modal, Space, Table, Tag, Typography } from "antd";
import { DeleteOutlined, DownOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";

import { IDP_ALLOWED_TRANSITIONS, PROVISIONING_RESOURCE, idpState } from "./constants";
import { useRefreshOrganization } from "./use_refresh_organization";
import { IOrganizationIdentityProvider, IProvisionedOrganization, IdpLifecycleState } from "interfaces";

const TRANSITION_WARNINGS: Partial<Record<IdpLifecycleState, string>> = {
    active:
        "Partner learners will be able to sign in through this identity provider. Only activate it after a test login through it has succeeded.",
    disabled: "Nobody will be able to sign in through this identity provider until it is moved back to Testing or Active.",
    draft: "The identity provider will be disabled in Keycloak.",
};

const Copyable: React.FC<{ value: string | null }> = ({ value }) =>
    value ? <Typography.Text copyable code>{value}</Typography.Text> : <Typography.Text type="secondary">n/a</Typography.Text>;

// What an operator hands the partner's IT team to configure their side.
const ServiceProviderDetails: React.FC<{ idp: IOrganizationIdentityProvider }> = ({ idp }) => (
    <Descriptions column={1} size="small" bordered>
        {idp.protocol === "saml" ? (
            <>
                <Descriptions.Item label="SP entity ID">
                    <Copyable value={idp.service_provider.entity_id} />
                </Descriptions.Item>
                <Descriptions.Item label="ACS URL">
                    <Copyable value={idp.service_provider.redirect_uri} />
                </Descriptions.Item>
                <Descriptions.Item label="SP metadata URL">
                    <Copyable value={idp.service_provider.metadata_url} />
                </Descriptions.Item>
            </>
        ) : (
            <Descriptions.Item label="Redirect URI">
                <Copyable value={idp.service_provider.redirect_uri} />
            </Descriptions.Item>
        )}
        <Descriptions.Item label="Metadata source">
            <Typography.Text style={{ wordBreak: "break-all" }}>
                {idp.metadata_source.trimStart().startsWith("<") ? "Pasted XML document" : idp.metadata_source}
            </Typography.Text>
        </Descriptions.Item>
        <Descriptions.Item label="Metadata fetched">
            {idp.metadata_fetched_at ? dayjs(idp.metadata_fetched_at).format("YYYY-MM-DD HH:mm") : "never"}
        </Descriptions.Item>
        <Descriptions.Item label="Keycloak internal ID">
            <Copyable value={idp.internal_id || null} />
        </Descriptions.Item>
    </Descriptions>
);

export const IdentityProviders: React.FC<{ organization: IProvisionedOrganization }> = ({ organization }) => {
    const apiUrl = useApiUrl();
    const go = useGo();
    const { mutate, isLoading } = useCustomMutation();
    const base = `${apiUrl}/${PROVISIONING_RESOURCE}/${organization.org_key}/identity-providers`;

    const refresh = useRefreshOrganization(organization.org_key);

    const confirmAndRun = (title: string, content: string, run: () => void) =>
        Modal.confirm({ title, content, onOk: run });

    const transition = (idp: IOrganizationIdentityProvider, state: IdpLifecycleState) =>
        confirmAndRun(
            `Move ${idp.alias} to ${idpState(state)?.label ?? state}?`,
            TRANSITION_WARNINGS[state] ?? "",
            () =>
                mutate(
                    {
                        url: `${base}/${idp.alias}/transition/`,
                        method: "post",
                        values: { state },
                        successNotification: { type: "success", message: `${idp.alias} is now ${idpState(state)?.label ?? state}` },
                    },
                    { onSuccess: refresh },
                ),
        );

    const refreshMetadata = (idp: IOrganizationIdentityProvider) =>
        confirmAndRun(
            `Refresh ${idp.alias}'s metadata?`,
            "Keycloak re-reads the partner's metadata from the stored source and updates the identity provider's config.",
            () =>
                mutate(
                    {
                        url: `${base}/${idp.alias}/refresh-metadata/`,
                        method: "post",
                        values: {},
                        successNotification: { type: "success", message: "Metadata refreshed" },
                    },
                    { onSuccess: refresh },
                ),
        );

    const remove = (idp: IOrganizationIdentityProvider) =>
        confirmAndRun(
            `Delete ${idp.alias}?`,
            "This deletes the identity provider from Keycloak. Users who sign in through it will no longer be able to, and the configuration cannot be recovered.",
            () =>
                mutate(
                    {
                        url: `${base}/${idp.alias}/`,
                        method: "delete",
                        values: {},
                        successNotification: { type: "success", message: `${idp.alias} deleted` },
                    },
                    { onSuccess: refresh },
                ),
        );

    return (
        <Card
            title="Identity providers"
            extra={
                <Button
                    icon={<PlusOutlined />}
                    onClick={() => go({ to: `/b2b_organizations/show/${organization.org_key}/identity-providers/create` })}
                >
                    Add identity provider
                </Button>
            }
        >
            <Table<IOrganizationIdentityProvider>
                dataSource={organization.identity_providers}
                rowKey="alias"
                pagination={false}
                locale={{ emptyText: "No identity provider. That is fine for an organization without SSO." }}
                expandable={{ expandedRowRender: (idp) => <ServiceProviderDetails idp={idp} /> }}
            >
                <Table.Column dataIndex="alias" title="Alias" />
                <Table.Column dataIndex="display_name" title="Display name" />
                <Table.Column<IOrganizationIdentityProvider>
                    title="Protocol"
                    render={(_, idp) => idp.protocol.toUpperCase()}
                />
                <Table.Column<IOrganizationIdentityProvider>
                    title="State"
                    render={(_, idp) => {
                        const state = idpState(idp.lifecycle_state);
                        return <Tag color={state?.color}>{state?.label ?? idp.lifecycle_state}</Tag>;
                    }}
                />
                <Table.Column<IOrganizationIdentityProvider>
                    title="Actions"
                    render={(_, idp) => (
                        <Space>
                            <Dropdown
                                disabled={isLoading || !IDP_ALLOWED_TRANSITIONS[idp.lifecycle_state]}
                                menu={{
                                    items: (IDP_ALLOWED_TRANSITIONS[idp.lifecycle_state] ?? []).map((state) => ({
                                        key: state,
                                        label: idpState(state)?.label ?? state,
                                    })),
                                    onClick: ({ key }) => transition(idp, key as IdpLifecycleState),
                                }}
                            >
                                <Button size="small">
                                    Move to <DownOutlined />
                                </Button>
                            </Dropdown>
                            <Button size="small" icon={<ReloadOutlined />} disabled={isLoading} onClick={() => refreshMetadata(idp)}>
                                Refresh metadata
                            </Button>
                            <Button size="small" danger icon={<DeleteOutlined />} disabled={isLoading} onClick={() => remove(idp)} />
                        </Space>
                    )}
                />
            </Table>
        </Card>
    );
};
