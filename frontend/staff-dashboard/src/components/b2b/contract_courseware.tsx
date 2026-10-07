import React from "react";
import { useCustomMutation } from "@refinedev/core";
import { Alert, Button, Card, Checkbox, Descriptions, Form, Input, Modal, Space, Table, Tag, Typography } from "antd";
import { DeleteOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";

import { CLONE_STATUSES, CONTRACT_SETUP_STATUSES, apiErrorNotification } from "./constants";
import {
    IContractRunSetup,
    IContractSetupStatus,
    ICoursewareAddition,
    IProvisionedContract,
    IRemovedContractRun,
} from "interfaces";

interface ICoursewareForm {
    courseware_id: string;
    remove_program_runs: boolean;
}

interface IContractCoursewareProps {
    // The contract's API URL, without a trailing slash.
    contractUrl: string;
    contract: IProvisionedContract;
    setupStatus?: IContractSetupStatus;
    refresh: () => void;
}

// Zero runs is not a failure: a program added again is still linked, and a
// course whose run is already in the contract is left as it is.
const additionSummary = ({ data }: { data: ICoursewareAddition }) => ({
    type: "success" as const,
    message: data.runs_added
        ? `${data.runs_added} contract run${data.runs_added === 1 ? "" : "s"} added`
        : "No new contract runs",
    description:
        [
            data.courses_without_source_run
                ? `${data.courses_without_source_run} course${data.courses_without_source_run === 1 ? " has" : "s have"} no source run to clone.`
                : "",
            data.skipped_reason,
        ]
            .filter(Boolean)
            .join(" ") || (data.runs_added ? undefined : "The contract already has a run for this courseware."),
});

const removalSummary = ({ data }: { data: IRemovedContractRun[] }) => {
    const kept = data.filter((run) => !run.unlinked);

    if (data.length === 0) {
        return {
            type: "success" as const,
            message: "Removed from the contract",
            description: "No contract runs were closed.",
        };
    }

    return {
        type: "success" as const,
        message: `${data.length} contract run${data.length === 1 ? "" : "s"} closed to new enrollments or unlinked`,
        description: kept.length
            ? `Still linked to the contract because learners are enrolled: ${kept.map((run) => run.courseware_id).join(", ")}`
            : undefined,
    };
};

// course-v1:ORG+COURSE is a course, course-v1:ORG+COURSE+RUN a run of it.
const isCourseRunId = (courseware_id: string) => /^course-v1:[^+]+\+[^+]+\+[^+]+$/.test(courseware_id);

// A contract write returns once MITx Online's rows exist. The edX clones and
// the enrollment codes follow in Celery, so this shows how far they have got.
export const ContractCourseware: React.FC<IContractCoursewareProps> = ({ contractUrl, contract, setupStatus, refresh }) => {
    const [form] = Form.useForm<ICoursewareForm>();
    const { mutate, isLoading } = useCustomMutation();
    const status = setupStatus && CONTRACT_SETUP_STATUSES[setupStatus.status];
    const codes = setupStatus?.enrollment_codes;
    const codesShort = !!codes && codes.existing < codes.expected;

    const postAddition = (courseware_id: string) =>
        mutate(
            {
                url: `${contractUrl}/courseware/`,
                method: "post",
                values: { courseware_id },
                successNotification: (response) => additionSummary(response as { data: ICoursewareAddition }),
                errorNotification: apiErrorNotification(`Could not add ${courseware_id}`),
            },
            {
                onSuccess: () => {
                    form.resetFields();
                    refresh();
                },
            },
        );

    // A program or course gets new contract runs cloned for it. A course run
    // is different: that run itself is moved into the contract.
    const add = (values: ICoursewareForm) => {
        const courseware_id = values.courseware_id.trim();
        if (!isCourseRunId(courseware_id)) {
            postAddition(courseware_id);
            return;
        }
        Modal.confirm({
            title: `Attach the existing run ${courseware_id}?`,
            content:
                "This looks like a course run ID, not a course ID. No new run is cloned: this run itself is attached to the contract as it is. Removing it from the contract later closes it to new enrollments and deactivates its products. To give the contract its own run of a course, enter the course ID instead.",
            okText: "Attach this run",
            onOk: () => postAddition(courseware_id),
        });
    };

    const remove = (courseware_id: string, remove_program_runs: boolean) =>
        Modal.confirm({
            title: `Remove ${courseware_id} from ${contract.name}?`,
            content: remove_program_runs
                ? "If this is a program, it is unlinked from the contract and its courses' contract runs are closed. A closed run takes no new enrollments, its products are deactivated, and its unassigned, unredeemed enrollment codes are deleted. A run with enrolled learners stays linked to the contract so they keep their course. A run another contract also uses is not closed, only unlinked from this one."
                : "If this is a program, it is only unlinked from the contract: its courses' contract runs stay open. A course or course run is closed: it takes no new enrollments, its products are deactivated, and its unassigned, unredeemed enrollment codes are deleted. A run with enrolled learners stays linked to the contract so they keep their course. A run another contract also uses is not closed, only unlinked from this one.",
            okButtonProps: { danger: true },
            okText: "Remove",
            onOk: () =>
                mutate(
                    {
                        url: `${contractUrl}/courseware/remove/`,
                        method: "post",
                        values: { courseware_id, remove_program_runs },
                        successNotification: (response) => removalSummary(response as { data: IRemovedContractRun[] }),
                        errorNotification: apiErrorNotification(`Could not remove ${courseware_id}`),
                    },
                    {
                        onSuccess: () => {
                            form.resetFields();
                            refresh();
                        },
                    },
                ),
        });

    const removeFromForm = async () => {
        try {
            const values = await form.validateFields();
            remove(values.courseware_id.trim(), !!values.remove_program_runs);
        } catch {
            // The form already shows what is missing.
        }
    };

    const retry = () =>
        mutate(
            {
                url: `${contractUrl}/retry-setup/`,
                method: "post",
                values: {},
                successNotification: { type: "success", message: "Failed clones and the enrollment code check are queued again" },
                errorNotification: apiErrorNotification("Could not retry setup"),
            },
            { onSuccess: refresh },
        );

    return (
        <Card
            title="Courseware and setup"
            extra={
                <Button icon={<ReloadOutlined />} onClick={retry} disabled={isLoading || !setupStatus || setupStatus.status === "complete"}>
                    Retry setup
                </Button>
            }
        >
            <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                <Descriptions column={1} size="small">
                    <Descriptions.Item label="Setup">
                        {status ? <Tag color={status.color}>{status.label}</Tag> : "Loading"}
                    </Descriptions.Item>
                    <Descriptions.Item label="Enrollment codes">
                        {codes ? (codes.expected ? `${codes.existing} of ${codes.expected}` : "Not used by this contract") : "Loading"}
                    </Descriptions.Item>
                    <Descriptions.Item label="Programs">
                        {contract.programs.length === 0 ? (
                            "none"
                        ) : (
                            <Space direction="vertical" size={0}>
                                {contract.programs.map((program) => (
                                    <span key={program.readable_id}>
                                        {program.title} <Typography.Text code copyable>{program.readable_id}</Typography.Text>
                                    </span>
                                ))}
                            </Space>
                        )}
                    </Descriptions.Item>
                </Descriptions>

                {codesShort && (
                    <Alert
                        type="info"
                        showIcon
                        message={`This contract has ${codes?.existing} of the ${codes?.expected} enrollment codes its courseware needs. They are created in the background after courseware is added. If the count is not moving, e.g. after expiring codes, Retry setup creates the missing ones.`}
                    />
                )}
                {setupStatus?.status === "failed" && (
                    <Alert
                        type="error"
                        showIcon
                        message="An edX clone failed. Learners cannot use that run until it is cloned. Check the error on the run, then retry setup."
                    />
                )}

                <Table<IContractRunSetup>
                    dataSource={setupStatus?.runs}
                    loading={!setupStatus}
                    rowKey="courseware_id"
                    size="small"
                    pagination={{ pageSize: 25, hideOnSinglePage: true, showSizeChanger: false }}
                    locale={{ emptyText: "No contract runs. Add a program, course or course run below." }}
                >
                    <Table.Column<IContractRunSetup>
                        title="Contract run"
                        render={(_, run) => <Typography.Text code copyable>{run.courseware_id}</Typography.Text>}
                    />
                    <Table.Column<IContractRunSetup>
                        title="edX clone"
                        render={(_, run) =>
                            run.clone_status ? (
                                <Tag color={CLONE_STATUSES[run.clone_status].color}>{CLONE_STATUSES[run.clone_status].label}</Tag>
                            ) : (
                                <Typography.Text type="secondary">Not tracked</Typography.Text>
                            )
                        }
                    />
                    <Table.Column dataIndex="clone_attempts" title="Attempts" />
                    <Table.Column<IContractRunSetup>
                        title="Last error"
                        render={(_, run) => <Typography.Text style={{ wordBreak: "break-word" }}>{run.clone_error}</Typography.Text>}
                    />
                    <Table.Column<IContractRunSetup>
                        title="Actions"
                        render={(_, run) => (
                            <Button
                                size="small"
                                danger
                                icon={<DeleteOutlined />}
                                aria-label={`Remove ${run.courseware_id} from the contract`}
                                disabled={isLoading}
                                onClick={() => remove(run.courseware_id, false)}
                            />
                        )}
                    />
                </Table>

                <Form<ICoursewareForm> form={form} layout="vertical" onFinish={add} initialValues={{ remove_program_runs: false }}>
                    <Form.Item
                        label="Program, course or course run"
                        name="courseware_id"
                        rules={[{ required: true, whitespace: true, message: "Enter a readable ID." }]}
                        extra="A readable ID, e.g. program-v1:MITx+DEDP or course-v1:MITx+14.100x. Adding creates a contract run for each course, cloned from its source run in edX. Adding the same courseware again does not create a second run."
                    >
                        <Input style={{ maxWidth: 480 }} />
                    </Form.Item>
                    <Form.Item name="remove_program_runs" valuePropName="checked">
                        <Checkbox>When removing a program, also remove its courses' runs</Checkbox>
                    </Form.Item>
                    <Space>
                        <Button type="primary" htmlType="submit" icon={<PlusOutlined />} loading={isLoading}>
                            Add to contract
                        </Button>
                        <Button danger onClick={removeFromForm} disabled={isLoading}>
                            Remove from contract
                        </Button>
                    </Space>
                </Form>
            </Space>
        </Card>
    );
};
