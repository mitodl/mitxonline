import React, { useState } from "react";
import { Create } from "@refinedev/antd";
import { useApiUrl, useCustomMutation, useGo, useParsed } from "@refinedev/core";
import { Alert, Button, Card, Descriptions, Form, Input, Radio, Select, Space, Typography } from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";

import { B2B_ORGANIZATIONS, IDP_PROTOCOLS, PROVISIONING_RESOURCE } from "components/b2b/constants";
import { useRefreshOrganization } from "components/b2b/use_refresh_organization";
import { IdpProtocol } from "interfaces";

type MetadataSource = "url" | "xml";

interface IAttributeRow {
    user_attribute: string;
    source: string;
    // SAML only: match the assertion attribute by FriendlyName or by Name.
    match?: "friendly" | "name";
}

interface IIdentityProviderForm {
    protocol: IdpProtocol;
    alias: string;
    display_name: string;
    metadata_source: MetadataSource;
    metadata_url: string;
    metadata_xml: string;
    discovery_url: string;
    client_id: string;
    client_secret: string;
    attributes: IAttributeRow[];
}

// A starting point for SAML. Partners name these attributes differently, so
// check them against the partner's metadata or a test login.
const DEFAULT_SAML_ATTRIBUTES: IAttributeRow[] = [
    { user_attribute: "email", source: "email", match: "friendly" },
    { user_attribute: "firstName", source: "firstName", match: "friendly" },
    { user_attribute: "lastName", source: "lastName", match: "friendly" },
];

const toMap = (rows: IAttributeRow[] | undefined, match: "friendly" | "name") =>
    Object.fromEntries(
        (rows ?? [])
            .filter((row) => row?.user_attribute && row?.source && (row.match ?? "friendly") === match)
            .map((row) => [row.user_attribute, row.source]),
    );

export const IdentityProviderCreate: React.FC = () => {
    const { params } = useParsed<{ orgKey: string }>();
    const orgKey = params?.orgKey as string;
    const apiUrl = useApiUrl();
    const go = useGo();
    const refresh = useRefreshOrganization(orgKey);
    const [form] = Form.useForm<IIdentityProviderForm>();
    const protocol = Form.useWatch("protocol", form);
    const metadataSource = Form.useWatch("metadata_source", form);
    const [parsed, setParsed] = useState<Record<string, string> | null>(null);
    const { mutate: parse, isLoading: parsing } = useCustomMutation<{ config: Record<string, string> }>();
    const { mutate: create, isLoading: creating } = useCustomMutation();

    const metadataPayload = (values: IIdentityProviderForm) =>
        values.protocol === "oidc"
            ? { metadata_url: values.discovery_url }
            : values.metadata_source === "xml"
                ? { metadata_xml: values.metadata_xml }
                : { metadata_url: values.metadata_url };

    const onParse = async () => {
        const fields = form.getFieldValue("protocol") === "oidc"
            ? ["discovery_url"]
            : [form.getFieldValue("metadata_source") === "xml" ? "metadata_xml" : "metadata_url"];
        try {
            await form.validateFields(fields);
        } catch {
            // The form already shows what is missing.
            return;
        }
        const values = form.getFieldsValue(true) as IIdentityProviderForm;
        parse(
            {
                url: `${apiUrl}/v0/b2b/provisioning/parse-metadata/`,
                method: "post",
                values: { protocol: values.protocol, ...metadataPayload(values) },
                errorNotification: { type: "error", message: "Keycloak could not parse that metadata" },
            },
            { onSuccess: ({ data }) => setParsed(data.config) },
        );
    };

    const onFinish = (values: IIdentityProviderForm) => {
        const payload =
            values.protocol === "oidc"
                ? {
                    protocol: values.protocol,
                    alias: values.alias,
                    display_name: values.display_name,
                    discovery_url: values.discovery_url,
                    client_id: values.client_id,
                    client_secret: values.client_secret,
                    attribute_map: toMap(values.attributes, "friendly"),
                }
                : {
                    protocol: values.protocol,
                    alias: values.alias,
                    display_name: values.display_name,
                    ...metadataPayload(values),
                    attribute_map: toMap(values.attributes, "friendly"),
                    attribute_name_map: toMap(values.attributes, "name"),
                };
        create(
            {
                url: `${apiUrl}/${PROVISIONING_RESOURCE}/${orgKey}/identity-providers/`,
                method: "post",
                values: payload,
                successNotification: {
                    type: "success",
                    message: `${values.alias} created in Draft`,
                    description: "Move it to Testing to try a login through it.",
                },
            },
            {
                onSuccess: () => {
                    refresh();
                    go({ to: { resource: B2B_ORGANIZATIONS, action: "show", id: orgKey } });
                },
            },
        );
    };

    return (
        <Create
            title={`Add identity provider to ${orgKey}`}
            saveButtonProps={{ onClick: () => form.submit(), loading: creating }}
        >
            <Form<IIdentityProviderForm>
                form={form}
                layout="vertical"
                onFinish={onFinish}
                onValuesChange={(changed) => {
                    if ("protocol" in changed) {
                        form.setFieldValue("attributes", changed.protocol === "saml" ? DEFAULT_SAML_ATTRIBUTES : []);
                    }
                    if ("protocol" in changed || "metadata_source" in changed || "metadata_url" in changed ||
                        "metadata_xml" in changed || "discovery_url" in changed) {
                        setParsed(null);
                    }
                }}
                initialValues={{ protocol: "saml", metadata_source: "url", attributes: DEFAULT_SAML_ATTRIBUTES }}
            >
                <Form.Item label="Protocol" name="protocol">
                    <Radio.Group optionType="button" options={IDP_PROTOCOLS} />
                </Form.Item>
                <Form.Item
                    label="Alias"
                    name="alias"
                    rules={[{ required: true }, { pattern: /^[A-Za-z0-9_-]+$/, message: "Letters, digits, hyphens and underscores only." }]}
                    extra="Must be unique across the whole Keycloak realm, and cannot be changed here later. It appears in the SP URLs the partner configures."
                >
                    <Input placeholder={orgKey?.toLowerCase()} />
                </Form.Item>
                <Form.Item label="Display name" name="display_name">
                    <Input />
                </Form.Item>

                {protocol === "oidc" ? (
                    <>
                        <Form.Item label="Discovery URL" name="discovery_url" rules={[{ required: true, type: "url" }]}>
                            <Input placeholder="https://idp.example.edu/.well-known/openid-configuration" />
                        </Form.Item>
                        <Form.Item label="Client ID" name="client_id" rules={[{ required: true }]}>
                            <Input />
                        </Form.Item>
                        <Form.Item
                            label="Client secret"
                            name="client_secret"
                            rules={[{ required: true }]}
                            extra="Sent to Keycloak only. MITx Online does not store it and cannot show it again."
                        >
                            <Input.Password autoComplete="off" />
                        </Form.Item>
                    </>
                ) : (
                    <>
                        <Form.Item label="Metadata" name="metadata_source">
                            <Radio.Group
                                optionType="button"
                                options={[{ value: "url", label: "URL" }, { value: "xml", label: "Paste XML" }]}
                            />
                        </Form.Item>
                        {metadataSource === "xml" ? (
                            <Form.Item label="Metadata XML" name="metadata_xml" rules={[{ required: true }]}>
                                <Input.TextArea rows={8} style={{ fontFamily: "monospace" }} />
                            </Form.Item>
                        ) : (
                            <Form.Item label="Metadata URL" name="metadata_url" rules={[{ required: true, type: "url" }]}>
                                <Input placeholder="https://idp.example.edu/metadata.xml" />
                            </Form.Item>
                        )}
                    </>
                )}

                <Card size="small" style={{ marginBottom: 24 }}>
                    <Space direction="vertical" style={{ width: "100%" }}>
                        <Button onClick={onParse} loading={parsing}>
                            Check what Keycloak reads from this metadata
                        </Button>
                        {parsed && (
                            Object.keys(parsed).length === 0 ? (
                                <Alert type="warning" showIcon message="Keycloak parsed the metadata but found no settings in it." />
                            ) : (
                                <Descriptions column={1} size="small" bordered>
                                    {Object.entries(parsed).map(([key, value]) => (
                                        <Descriptions.Item key={key} label={key}>
                                            <Typography.Text style={{ wordBreak: "break-all" }}>{String(value)}</Typography.Text>
                                        </Descriptions.Item>
                                    ))}
                                </Descriptions>
                            )
                        )}
                    </Space>
                </Card>

                <Typography.Title level={5}>Attribute mapping</Typography.Title>
                <Typography.Paragraph type="secondary">
                    {protocol === "oidc"
                        ? "Optional for OIDC: map a user attribute to a claim in the partner's token."
                        : "Required for SAML: without it, users arrive with no email or name. Match each SAML attribute by its FriendlyName, or by its Name when the partner's assertions only carry URI names."}
                </Typography.Paragraph>
                <Form.List name="attributes">
                    {(fields, { add, remove }) => (
                        <>
                            {fields.map(({ key, name }) => (
                                <Space key={key} align="baseline" style={{ display: "flex" }}>
                                    <Form.Item name={[name, "user_attribute"]} rules={[{ required: true }]}>
                                        <Input placeholder="User attribute, e.g. email" />
                                    </Form.Item>
                                    {protocol !== "oidc" && (
                                        <Form.Item name={[name, "match"]} initialValue="friendly">
                                            <Select
                                                style={{ width: 150 }}
                                                options={[
                                                    { value: "friendly", label: "FriendlyName" },
                                                    { value: "name", label: "Name" },
                                                ]}
                                            />
                                        </Form.Item>
                                    )}
                                    <Form.Item name={[name, "source"]} rules={[{ required: true }]}>
                                        <Input placeholder={protocol === "oidc" ? "Claim" : "SAML attribute"} />
                                    </Form.Item>
                                    <MinusCircleOutlined onClick={() => remove(name)} />
                                </Space>
                            ))}
                            <Button type="dashed" onClick={() => add()} icon={<PlusOutlined />}>
                                Add mapping
                            </Button>
                        </>
                    )}
                </Form.List>
            </Form>
        </Create>
    );
};
