import React from "react";
import { Button, Form, Input, Select, Space, Typography } from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";

import { IdpProtocol } from "interfaces";

type AttributeMatch = "friendly" | "name";

export interface IAttributeRow {
    user_attribute: string;
    source: string;
    // SAML only: match the assertion attribute by FriendlyName or by Name.
    match?: AttributeMatch;
}

export const toMap = (rows: IAttributeRow[] | undefined, match: AttributeMatch) =>
    Object.fromEntries(
        (rows ?? [])
            .filter((row) => row?.user_attribute && row?.source && (row.match ?? "friendly") === match)
            .map((row) => [row.user_attribute, row.source]),
    );

const toRows = (map: Record<string, string>, match: AttributeMatch): IAttributeRow[] =>
    Object.entries(map).map(([user_attribute, source]) => ({ user_attribute, source, match }));

export const fromMaps = (
    attributeMap: Record<string, string>,
    attributeNameMap: Record<string, string>,
): IAttributeRow[] => [...toRows(attributeMap, "friendly"), ...toRows(attributeNameMap, "name")];

// The rows of a Form.List named "attributes".
export const AttributeMapping: React.FC<{ protocol: IdpProtocol }> = ({ protocol }) => (
    <>
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
                            <Button type="text" icon={<MinusCircleOutlined />} aria-label="Remove mapping" onClick={() => remove(name)} />
                        </Space>
                    ))}
                    <Button type="dashed" onClick={() => add()} icon={<PlusOutlined />}>
                        Add mapping
                    </Button>
                </>
            )}
        </Form.List>
    </>
);
