import React from "react";
import { Form, FormProps, Input, Select } from "antd";

interface IOrganizationFormProps {
    formProps: FormProps;
    creating: boolean;
}

export const OrganizationForm: React.FC<IOrganizationFormProps> = ({ formProps, creating }) => (
    <Form {...formProps} layout="vertical">
        <Form.Item label="Name" name="name" rules={[{ required: true }]}>
            <Input />
        </Form.Item>
        {/* org_key is only sent on create: the update endpoint rejects it. */}
        {creating && (
            <>
                <Form.Item
                    label="Org key"
                    name="org_key"
                    rules={[{ required: true, max: 30 }]}
                    extra="Part of every courseware ID for this organization, so it cannot change after the organization is created."
                >
                    <Input />
                </Form.Item>
                <Form.Item label="Org key prefix" name="org_key_prefix" rules={[{ max: 30 }]}>
                    <Input placeholder="UAI_" />
                </Form.Item>
            </>
        )}
        <Form.Item
            label="Email domains"
            name="domains"
            extra="Written to the Keycloak organization as verified domains. Nothing checks that the partner owns them, so confirm with the partner first."
        >
            <Select mode="tags" tokenSeparators={[",", " "]} placeholder="example.edu" open={false} />
        </Form.Item>
        <Form.Item label="Post-login redirect URL" name="redirect_url" rules={[{ type: "url" }]}>
            <Input placeholder="https://learn.mit.edu/dashboard/organization/..." />
        </Form.Item>
        <Form.Item label="Description" name="description">
            <Input.TextArea rows={3} />
        </Form.Item>
    </Form>
);
