import React, { useEffect, useState } from "react";
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Alert, Button, Card, Form, Input, Modal, Space, Table, Tag, Typography } from "antd";
import dayjs from "dayjs";

import { apiErrorNotification } from "./constants";
import {
    IBulkAssignResult,
    IContractEnrollmentCode,
    IExpiredEnrollmentCode,
    IPage,
    IProvisionedContract,
} from "interfaces";

const PAGE_SIZE = 25;

const REDEMPTION_STATUSES: Record<IContractEnrollmentCode["redemption_status"], { label: string; color: string }> = {
    unassigned: { label: "Unassigned", color: "default" },
    assigned: { label: "Assigned", color: "blue" },
    redeemed: { label: "Redeemed", color: "green" },
};

const formatTime = (value: string | null) => (value ? dayjs(value).format("YYYY-MM-DD HH:mm") : "");

// One "email, name" per line. The name is optional.
const parseRecipients = (text: string) =>
    text
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
            const [email, ...name] = line.split(",");
            return { email: email.trim(), name: name.join(",").trim() };
        });

interface IContractCodesProps {
    // The contract's API URL, without a trailing slash.
    contractUrl: string;
    contract: IProvisionedContract;
    // How many codes setup-status last counted. They are generated in Celery,
    // so the list is stale whenever this moves.
    existingCodes?: number;
    refresh: () => void;
}

export const ContractCodes: React.FC<IContractCodesProps> = ({ contractUrl, contract, existingCodes, refresh }) => {
    const [page, setPage] = useState(1);
    const [assigning, setAssigning] = useState(false);
    const [assignErrors, setAssignErrors] = useState<IBulkAssignResult["errors"]>([]);
    const [form] = Form.useForm<{ recipients: string }>();
    const { mutate, isLoading } = useCustomMutation();
    const { data, isFetching, refetch } = useCustom<IPage<IContractEnrollmentCode>>({
        url: `${contractUrl}/codes/`,
        method: "get",
        config: { query: { page, page_size: PAGE_SIZE } },
    });

    // Back to the first page: the page being shown may no longer exist once
    // codes have been expired or a run removed, and DRF answers that with 404.
    const reload = () => (page === 1 ? refetch() : setPage(1));

    const listedCodes = data?.data.count;
    useEffect(() => {
        if (existingCodes !== undefined && listedCodes !== undefined && existingCodes !== listedCodes) {
            reload();
        }
    }, [existingCodes, listedCodes]);

    const refreshCodes = () => {
        reload();
        refresh();
    };

    const expire = () =>
        Modal.confirm({
            title: `Expire ${contract.name}'s unused enrollment codes?`,
            content:
                "Codes that have been neither assigned nor redeemed are taken out of the contract. A code already assigned to someone keeps working, and so does a redeemed one. The contract is then short of codes, and replacements are created the next time its enrollment code check runs: on Retry setup, on an edit to the contract, or when courseware is added.",
            okButtonProps: { danger: true },
            okText: "Expire unused codes",
            onOk: () =>
                mutate(
                    {
                        url: `${contractUrl}/codes/expire/`,
                        method: "post",
                        values: {},
                        successNotification: (response) => {
                            const expired = (response as { data: IExpiredEnrollmentCode[] }).data;
                            return { type: "success", message: `${expired.length} unused code${expired.length === 1 ? "" : "s"} expired` };
                        },
                        errorNotification: apiErrorNotification("Could not expire the codes"),
                    },
                    { onSuccess: refreshCodes },
                ),
        });

    const assign = ({ recipients }: { recipients: string }) =>
        mutate(
            {
                url: `${contractUrl}/codes/assign/`,
                method: "post",
                values: parseRecipients(recipients),
                successNotification: (response) => {
                    const { assigned } = (response as { data: IBulkAssignResult }).data;
                    return { type: "success", message: `${assigned.length} code${assigned.length === 1 ? "" : "s"} assigned and emailed` };
                },
                errorNotification: apiErrorNotification("Could not assign codes"),
            },
            {
                onSuccess: (response) => {
                    setAssignErrors((response.data as IBulkAssignResult).errors);
                    setAssigning(false);
                    form.resetFields();
                    refreshCodes();
                },
            },
        );

    return (
        <Card
            title="Enrollment codes"
            extra={
                <Space>
                    <Button onClick={() => setAssigning(true)} disabled={isLoading || !data?.data.count}>
                        Assign codes
                    </Button>
                    <Button danger onClick={expire} disabled={isLoading || !data?.data.count}>
                        Expire unused codes
                    </Button>
                </Space>
            }
        >
            {assignErrors.length > 0 && (
                <Alert
                    type="warning"
                    showIcon
                    closable
                    onClose={() => setAssignErrors([])}
                    style={{ marginBottom: 16 }}
                    message={`${assignErrors.length} ${assignErrors.length === 1 ? "person was" : "people were"} not assigned a code`}
                    description={
                        <ul style={{ margin: 0, paddingLeft: 20 }}>
                            {assignErrors.map((error) => (
                                <li key={error.email}>
                                    {error.email}: {error.detail}
                                </li>
                            ))}
                        </ul>
                    }
                />
            )}
            <Table<IContractEnrollmentCode>
                dataSource={data?.data.results}
                loading={isFetching}
                rowKey="id"
                size="small"
                locale={{ emptyText: "No enrollment codes." }}
                pagination={{
                    current: page,
                    pageSize: PAGE_SIZE,
                    total: data?.data.count,
                    onChange: setPage,
                    showSizeChanger: false,
                    showTotal: (total) => `${total} codes`,
                }}
            >
                <Table.Column<IContractEnrollmentCode>
                    title="Code"
                    render={(_, code) => <Typography.Text code copyable>{code.code}</Typography.Text>}
                />
                <Table.Column<IContractEnrollmentCode>
                    title="Status"
                    render={(_, code) => (
                        <Tag color={REDEMPTION_STATUSES[code.redemption_status]?.color}>
                            {REDEMPTION_STATUSES[code.redemption_status]?.label ?? code.redemption_status}
                        </Tag>
                    )}
                />
                <Table.Column<IContractEnrollmentCode>
                    title="Assigned to"
                    render={(_, code) => [code.assigned_name, code.assigned_to].filter(Boolean).join(" · ")}
                />
                <Table.Column<IContractEnrollmentCode> title="Assigned" render={(_, code) => formatTime(code.assigned_on)} />
                <Table.Column dataIndex="email_status" title="Email" />
                <Table.Column dataIndex="redeemed_by" title="Redeemed by" />
                <Table.Column<IContractEnrollmentCode> title="Redeemed" render={(_, code) => formatTime(code.redeemed_on)} />
            </Table>
            <Modal
                title={`Assign ${contract.name}'s enrollment codes`}
                open={assigning}
                onCancel={() => setAssigning(false)}
                onOk={() => form.submit()}
                okText="Assign and email"
                confirmLoading={isLoading}
            >
                <Form form={form} layout="vertical" onFinish={assign}>
                    <Form.Item
                        label="People"
                        name="recipients"
                        rules={[{ required: true, whitespace: true, message: "Enter at least one email address." }]}
                        extra="One per line: email, name. The name is optional. Each person is assigned a free code and emailed it."
                    >
                        <Input.TextArea rows={8} placeholder={"learner@example.edu, Ada Lovelace"} />
                    </Form.Item>
                </Form>
            </Modal>
        </Card>
    );
};
