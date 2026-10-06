import React from "react";
import { Edit } from "@refinedev/antd";
import { useApiUrl, useCustom, useCustomMutation, useGo, useParsed } from "@refinedev/core";
import { Descriptions, Form, Input, Radio, Typography } from "antd";

import { apiErrorDescription } from "components/b2b/api_error";
import { AttributeMapping, IAttributeRow, fromMaps, toMap } from "components/b2b/attribute_mapping";
import { B2B_ORGANIZATIONS, PROVISIONING_RESOURCE } from "components/b2b/constants";
import { useRefreshOrganization } from "components/b2b/use_refresh_organization";
import { IOrganizationIdentityProviderDetail } from "interfaces";

type MetadataChange = "keep" | "url" | "xml";

interface IIdentityProviderEditForm {
    display_name: string;
    metadata_change: MetadataChange;
    metadata_url: string;
    metadata_xml: string;
    discovery_url: string;
    client_id: string;
    client_secret: string;
    attributes: IAttributeRow[];
}

const sameMap = (a: Record<string, string>, b: Record<string, string>) =>
    JSON.stringify(Object.entries(a).sort()) === JSON.stringify(Object.entries(b).sort());

// Send only what the operator changed. The API rejects a blank everywhere but
// display_name, a metadata source that is sent is fetched and parsed again,
// and the attribute maps replace the IdP's whole mapper set.
const changedFields = (values: IIdentityProviderEditForm, idp: IOrganizationIdentityProviderDetail) => {
    const changes: Record<string, unknown> = {};
    const displayName = values.display_name ?? "";

    if (displayName !== idp.display_name) {
        changes.display_name = displayName;
    }

    if (idp.protocol === "oidc") {
        if (values.discovery_url && values.discovery_url !== idp.metadata_source) {
            changes.discovery_url = values.discovery_url;
        }
        if (values.client_id) {
            changes.client_id = values.client_id;
        }
        if (values.client_secret) {
            changes.client_secret = values.client_secret;
        }
    } else if (values.metadata_change === "url") {
        changes.metadata_url = values.metadata_url;
    } else if (values.metadata_change === "xml") {
        changes.metadata_xml = values.metadata_xml;
    }

    const attributeMap = toMap(values.attributes, "friendly");
    const attributeNameMap = toMap(values.attributes, "name");
    if (!sameMap(attributeMap, idp.attribute_map) || !sameMap(attributeNameMap, idp.attribute_name_map)) {
        changes.attribute_map = attributeMap;
        // SAML takes the two maps as a pair. OIDC rejects attribute_name_map.
        if (idp.protocol === "saml") {
            changes.attribute_name_map = attributeNameMap;
        }
    }

    return changes;
};

export const IdentityProviderEdit: React.FC = () => {
    const { params } = useParsed<{ orgKey: string; alias: string }>();
    const orgKey = params?.orgKey as string;
    const alias = params?.alias as string;
    const apiUrl = useApiUrl();
    const go = useGo();
    const refresh = useRefreshOrganization(orgKey);
    const [form] = Form.useForm<IIdentityProviderEditForm>();
    const metadataChange = Form.useWatch("metadata_change", form);
    const url = `${apiUrl}/${PROVISIONING_RESOURCE}/${orgKey}/identity-providers/${alias}/`;
    const { data, isLoading } = useCustom<IOrganizationIdentityProviderDetail>({
        url,
        method: "get",
        // The form's initial values are read once, so a cached copy from before
        // the last save would be edited as if it were current.
        // A retry only delays the error for an unknown alias or a Keycloak failure.
        queryOptions: { cacheTime: 0, retry: false },
        errorNotification: { type: "error", message: `Could not read ${alias} and its attribute mappers from Keycloak` },
    });
    const idp = data?.data;
    const { mutate: update, isLoading: updating } = useCustomMutation();

    const showOrganization = () => go({ to: { resource: B2B_ORGANIZATIONS, action: "show", id: orgKey } });

    const onFinish = (values: IIdentityProviderEditForm) => {
        if (!idp) {
            return;
        }
        const changes = changedFields(values, idp);
        if (Object.keys(changes).length === 0) {
            showOrganization();
            return;
        }
        update(
            {
                url,
                method: "patch",
                values: changes,
                successNotification: { type: "success", message: `${alias} updated` },
                errorNotification: (error) => ({
                    type: "error",
                    message: `Could not update ${alias}`,
                    description: apiErrorDescription(error),
                }),
            },
            {
                onSuccess: () => {
                    refresh();
                    showOrganization();
                },
            },
        );
    };

    return (
        <Edit
            title={`Edit identity provider ${alias}`}
            resource={B2B_ORGANIZATIONS}
            recordItemId={orgKey}
            isLoading={isLoading}
            headerButtons={<></>}
            canDelete={false}
            saveButtonProps={{ onClick: () => form.submit(), loading: updating, disabled: !idp }}
        >
            {idp && (
                <Form<IIdentityProviderEditForm>
                    form={form}
                    layout="vertical"
                    onFinish={onFinish}
                    initialValues={{
                        display_name: idp.display_name,
                        metadata_change: "keep",
                        discovery_url: idp.protocol === "oidc" ? idp.metadata_source : undefined,
                        attributes: fromMaps(idp.attribute_map, idp.attribute_name_map),
                    }}
                >
                    <Descriptions column={1} size="small" style={{ marginBottom: 24 }}>
                        <Descriptions.Item label="Alias">
                            <Typography.Text code>{idp.alias}</Typography.Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Protocol">{idp.protocol.toUpperCase()}</Descriptions.Item>
                    </Descriptions>
                    <Typography.Paragraph type="secondary">
                        The alias and protocol cannot be changed. Saving does not change the lifecycle state or
                        anyone's link to this identity provider.
                    </Typography.Paragraph>
                    <Form.Item label="Display name" name="display_name">
                        <Input />
                    </Form.Item>

                    {idp.protocol === "oidc" ? (
                        <>
                            <Form.Item
                                label="Discovery URL"
                                name="discovery_url"
                                rules={[{ required: true, type: "url" }]}
                                extra="Changing it makes Keycloak read the partner's endpoints from the new URL."
                            >
                                <Input />
                            </Form.Item>
                            <Form.Item label="Client ID" name="client_id" extra="Leave blank to keep the current client ID.">
                                <Input autoComplete="off" />
                            </Form.Item>
                            <Form.Item
                                label="Client secret"
                                name="client_secret"
                                extra="Leave blank to keep the current secret. A new one is sent to Keycloak only. MITx Online does not store it and cannot show it again."
                            >
                                <Input.Password autoComplete="new-password" />
                            </Form.Item>
                        </>
                    ) : (
                        <>
                            <Form.Item
                                label="Metadata"
                                name="metadata_change"
                                extra={
                                    metadataChange === "keep"
                                        ? `Current source: ${idp.metadata_source.trimStart().startsWith("<") ? "pasted XML document" : idp.metadata_source}`
                                        : "Keycloak parses the new metadata and it replaces the stored config."
                                }
                            >
                                <Radio.Group
                                    optionType="button"
                                    options={[
                                        { value: "keep", label: "Keep current" },
                                        { value: "url", label: "New URL" },
                                        { value: "xml", label: "Paste new XML" },
                                    ]}
                                />
                            </Form.Item>
                            {metadataChange === "url" && (
                                <Form.Item label="Metadata URL" name="metadata_url" rules={[{ required: true, type: "url" }]}>
                                    <Input placeholder="https://idp.example.edu/metadata.xml" />
                                </Form.Item>
                            )}
                            {metadataChange === "xml" && (
                                <Form.Item label="Metadata XML" name="metadata_xml" rules={[{ required: true }]}>
                                    <Input.TextArea rows={8} style={{ fontFamily: "monospace" }} />
                                </Form.Item>
                            )}
                        </>
                    )}

                    <AttributeMapping protocol={idp.protocol} />
                </Form>
            )}
        </Edit>
    );
};
