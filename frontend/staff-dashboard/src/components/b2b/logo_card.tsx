import React from "react";
import { useApiUrl, useCustomMutation } from "@refinedev/core";
import { DeleteOutlined, UploadOutlined } from "@ant-design/icons";
import { Button, Card, Image, Modal, Space, Typography, Upload } from "antd";

import { PROVISIONING_RESOURCE, apiErrorNotification } from "./constants";
import { useRefreshOrganization } from "./use_refresh_organization";
import { IProvisionedOrganization } from "interfaces";

// The logo is stored only in MITx Online, so a change takes effect here
// without touching Keycloak and works for an organization that isn't linked.
export const LogoCard: React.FC<{ organization: IProvisionedOrganization }> = ({ organization }) => {
    const apiUrl = useApiUrl();
    const refresh = useRefreshOrganization(organization.org_key);
    const { mutate, isLoading } = useCustomMutation();
    const url = `${apiUrl}/${PROVISIONING_RESOURCE}/${organization.org_key}/logo/`;

    const upload = (file: File) => {
        const values = new FormData();
        values.append("logo", file);
        mutate(
            {
                url,
                method: "put",
                values,
                successNotification: { type: "success", message: "Logo saved" },
                errorNotification: apiErrorNotification("Could not save the logo"),
            },
            { onSuccess: refresh },
        );
        // Upload's own request is skipped; the mutation above sends the file.
        return false;
    };

    const remove = () =>
        Modal.confirm({
            title: `Remove ${organization.name}'s logo?`,
            content: "Learners in this organization will see no logo until a new one is uploaded.",
            onOk: () =>
                mutate(
                    {
                        url,
                        method: "delete",
                        values: {},
                        successNotification: { type: "success", message: "Logo removed" },
                        errorNotification: apiErrorNotification("Could not remove the logo"),
                    },
                    { onSuccess: refresh },
                ),
        });

    return (
        <Card title="Logo">
            <Space direction="vertical">
                {organization.logo ? (
                    <Image src={organization.logo} alt={`${organization.name} logo`} style={{ maxHeight: 80 }} />
                ) : (
                    <Typography.Text type="secondary">No logo</Typography.Text>
                )}
                <Space>
                    <Upload accept="image/*" showUploadList={false} beforeUpload={upload}>
                        <Button icon={<UploadOutlined />} loading={isLoading}>
                            {organization.logo ? "Replace logo" : "Upload logo"}
                        </Button>
                    </Upload>
                    {organization.logo && (
                        <Button danger icon={<DeleteOutlined />} onClick={remove} disabled={isLoading}>
                            Remove
                        </Button>
                    )}
                </Space>
            </Space>
        </Card>
    );
};
