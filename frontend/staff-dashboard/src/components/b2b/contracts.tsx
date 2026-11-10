import React, { useState } from "react";
import { useApiUrl, useCustom, useGo } from "@refinedev/core";
import { Button, Card, Table, Tag } from "antd";
import { PlusOutlined } from "@ant-design/icons";

import { contractPath, contractsUrl, membershipType, organizationPath } from "./constants";
import { IPage, IProvisionedContract, IProvisionedOrganization } from "interfaces";
import { formatIncome } from "utils";

const PAGE_SIZE = 25;

export const Contracts: React.FC<{ organization: IProvisionedOrganization }> = ({ organization }) => {
    const apiUrl = useApiUrl();
    const go = useGo();
    const [page, setPage] = useState(1);
    const { data, isFetching } = useCustom<IPage<IProvisionedContract>>({
        url: `${contractsUrl(apiUrl, organization.org_key)}/`,
        method: "get",
        config: { query: { page, page_size: PAGE_SIZE } },
    });

    return (
        <Card
            title="Contracts"
            extra={
                <Button
                    icon={<PlusOutlined />}
                    onClick={() => go({ to: `${organizationPath(organization.org_key)}/contracts/create` })}
                >
                    Add contract
                </Button>
            }
        >
            <Table<IProvisionedContract>
                dataSource={data?.data.results}
                loading={isFetching}
                rowKey="id"
                size="small"
                locale={{ emptyText: "No contracts yet." }}
                pagination={{
                    current: page,
                    pageSize: PAGE_SIZE,
                    total: data?.data.count,
                    onChange: setPage,
                    hideOnSinglePage: true,
                    showSizeChanger: false,
                }}
            >
                <Table.Column<IProvisionedContract>
                    title="Name"
                    render={(_, contract) => (
                        <Button
                            type="link"
                            style={{ padding: 0 }}
                            onClick={() => go({ to: contractPath(organization.org_key, contract.id) })}
                        >
                            {contract.name}
                        </Button>
                    )}
                />
                <Table.Column<IProvisionedContract>
                    title="Membership"
                    render={(_, contract) => membershipType(contract.membership_type)?.label ?? contract.membership_type}
                />
                <Table.Column<IProvisionedContract>
                    title="Dates"
                    render={(_, contract) => `${contract.contract_start ?? "no start"} to ${contract.contract_end ?? "no end"}`}
                />
                <Table.Column<IProvisionedContract>
                    title="Learners"
                    render={(_, contract) => contract.max_learners || "Unlimited"}
                />
                <Table.Column<IProvisionedContract>
                    title="Price"
                    render={(_, contract) =>
                        Number(contract.enrollment_fixed_price) ? formatIncome(contract.enrollment_fixed_price as string, "USD") : "Free"
                    }
                />
                <Table.Column<IProvisionedContract>
                    title="Active"
                    render={(_, contract) => (contract.active ? <Tag color="green">Active</Tag> : <Tag>Inactive</Tag>)}
                />
            </Table>
        </Card>
    );
};
