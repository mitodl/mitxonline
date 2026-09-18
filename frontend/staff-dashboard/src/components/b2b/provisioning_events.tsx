import React from "react";
import { useTable } from "@refinedev/antd";
import { Card, Table, Typography } from "antd";
import dayjs from "dayjs";

import { eventsResource } from "./constants";
import { IProvisioningEvent } from "interfaces";

const ACTION_LABELS: Record<string, string> = {
    organization_created: "Organization created",
    organization_updated: "Organization updated",
    onboarding_changed: "Onboarding state changed",
    identity_provider_created: "Identity provider created",
    identity_provider_transitioned: "Identity provider moved",
    identity_provider_metadata_refreshed: "Identity provider metadata refreshed",
    identity_provider_deleted: "Identity provider deleted",
};

const Snapshot: React.FC<{ title: string; data: Record<string, unknown> | null }> = ({ title, data }) =>
    data ? (
        <div style={{ flex: 1, minWidth: 0 }}>
            <Typography.Text strong>{title}</Typography.Text>
            <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-all", fontSize: 12 }}>
                {JSON.stringify(data, null, 2)}
            </pre>
        </div>
    ) : null;

// The append-only record of who changed this organization's provisioning,
// which stands in for the review trail a Pulumi PR used to give.
export const ProvisioningEvents: React.FC<{ orgKey: string }> = ({ orgKey }) => {
    const { tableProps } = useTable<IProvisioningEvent>({
        resource: eventsResource(orgKey),
        pagination: { pageSize: 10 },
        syncWithLocation: false,
    });

    return (
        <Card title="Change history">
            <Table<IProvisioningEvent>
                {...tableProps}
                rowKey="id"
                size="small"
                expandable={{
                    expandedRowRender: (event) => (
                        <div style={{ display: "flex", gap: 16 }}>
                            <Snapshot title="Before" data={event.data_before} />
                            <Snapshot title="After" data={event.data_after} />
                        </div>
                    ),
                    rowExpandable: (event) => !!(event.data_before || event.data_after),
                }}
            >
                <Table.Column<IProvisioningEvent>
                    title="When"
                    render={(_, event) => dayjs(event.created_on).format("YYYY-MM-DD HH:mm")}
                />
                <Table.Column<IProvisioningEvent>
                    title="Who"
                    render={(_, event) => event.actor?.email ?? event.actor?.username ?? "System"}
                />
                <Table.Column<IProvisioningEvent>
                    title="What"
                    render={(_, event) => ACTION_LABELS[event.action] ?? event.action}
                />
                <Table.Column dataIndex="identity_provider_alias" title="Identity provider" />
            </Table>
        </Card>
    );
};
