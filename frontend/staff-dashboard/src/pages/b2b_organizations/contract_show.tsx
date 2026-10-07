import React, { useEffect, useState } from "react";
import { Show } from "@refinedev/antd";
import { useApiUrl, useCustom, useGo, useParsed } from "@refinedev/core";
import { Button, Card, Col, Descriptions, Result, Row, Tag, Typography } from "antd";
import { EditOutlined, ExportOutlined, ReloadOutlined } from "@ant-design/icons";

import { contractPath, contractsUrl, membershipType, organizationPath } from "components/b2b/constants";
import { ContractCodes } from "components/b2b/contract_codes";
import { ContractCourseware } from "components/b2b/contract_courseware";
import { IContractSetupStatus, IProvisionedContract } from "interfaces";
import { formatIncome, mitxOnlineUrl } from "utils";

const SETUP_POLL_INTERVAL_MS = 5000;
// How long to wait for enrollment codes after the page loads or changes
// something. A contract can stay short of codes for good (e.g. after its
// unused ones are expired), so this cannot wait until the count is met.
const CODE_POLL_WINDOW_MS = 2 * 60 * 1000;

// Clones are checked individually: the API reports "failed" as soon as one
// clone fails, while others may still be running.
const shouldPoll = (setupStatus: IContractSetupStatus | undefined, waitingForCodes: boolean) =>
    !!setupStatus &&
    (setupStatus.runs.some((run) => run.clone_status === "pending" || run.clone_status === "cloning") ||
        (setupStatus.enrollment_codes.existing < setupStatus.enrollment_codes.expected && waitingForCodes));

// The description is Wagtail rich text. Show its text rather than its markup,
// without putting stored HTML into the page.
const richTextToPlain = (html: string) => new DOMParser().parseFromString(html, "text/html").body.textContent ?? "";

export const ContractShow: React.FC = () => {
    const { params } = useParsed<{ orgKey: string; contractId: string }>();
    const orgKey = params?.orgKey as string;
    const contractId = params?.contractId as string;
    const apiUrl = useApiUrl();
    const go = useGo();
    const contractUrl = `${contractsUrl(apiUrl, orgKey)}/${contractId}`;

    const contractQuery = useCustom<IProvisionedContract>({
        url: `${contractUrl}/`,
        method: "get",
        queryOptions: { retry: false },
    });
    const [codesDeadline, setCodesDeadline] = useState(() => Date.now() + CODE_POLL_WINDOW_MS);
    // State, not a comparison with the clock, so the page re-renders and can
    // say so when the wait ends.
    const [waitingForCodes, setWaitingForCodes] = useState(true);
    useEffect(() => {
        setWaitingForCodes(true);
        const timer = setTimeout(() => setWaitingForCodes(false), codesDeadline - Date.now());
        return () => clearTimeout(timer);
    }, [codesDeadline]);
    // edX clones and enrollment codes finish in Celery, so keep asking while
    // either is outstanding.
    const setupQuery = useCustom<IContractSetupStatus>({
        url: `${contractUrl}/setup-status/`,
        method: "get",
        queryOptions: {
            retry: false,
            refetchInterval: (response) => (shouldPoll(response?.data, waitingForCodes) ? SETUP_POLL_INTERVAL_MS : false),
        },
    });
    const contract = contractQuery.data?.data;
    const setupStatus = setupQuery.data?.data;

    const refresh = () => {
        setCodesDeadline(Date.now() + CODE_POLL_WINDOW_MS);
        contractQuery.refetch();
        setupQuery.refetch();
    };

    return (
        <Show
            isLoading={contractQuery.isLoading}
            title={contract?.name ?? "Contract"}
            goBack={null}
            breadcrumb={null}
            headerButtons={() => (
                <>
                    <Button onClick={() => go({ to: organizationPath(orgKey) })}>Back to {orgKey}</Button>
                    <Button icon={<ReloadOutlined />} onClick={refresh}>
                        Refresh
                    </Button>
                    {/* The welcome page's extra content, the Google Sheet target and program order are not in the contract API yet. */}
                    {contract && (
                        <Button icon={<ExportOutlined />} href={mitxOnlineUrl(`/cms/pages/${contract.id}/edit/`)} target="_blank">
                            Open in Wagtail
                        </Button>
                    )}
                    {contract && (
                        <Button type="primary" icon={<EditOutlined />} onClick={() => go({ to: `${contractPath(orgKey, contractId)}/edit` })}>
                            Edit
                        </Button>
                    )}
                </>
            )}
        >
            {contractQuery.isError && (
                <Result status="warning" title={`Could not load contract ${contractId} of ${orgKey}`} subTitle="Check that it exists and belongs to this organization." />
            )}
            {contract && (
                <Row gutter={[16, 16]}>
                    <Col span={24}>
                        <Card title="Contract">
                            <Descriptions column={{ xs: 1, lg: 2 }} size="small">
                                <Descriptions.Item label="Organization">
                                    <Typography.Text code>{orgKey}</Typography.Text>
                                </Descriptions.Item>
                                <Descriptions.Item label="Status">
                                    {contract.active ? <Tag color="green">Active</Tag> : <Tag>Inactive</Tag>}
                                </Descriptions.Item>
                                <Descriptions.Item label="Membership type">
                                    {membershipType(contract.membership_type)?.label ?? contract.membership_type}
                                </Descriptions.Item>
                                <Descriptions.Item label="Dates">
                                    {contract.contract_start ?? "no start"} to {contract.contract_end ?? "no end"}
                                </Descriptions.Item>
                                <Descriptions.Item label="Maximum learners">{contract.max_learners || "Unlimited"}</Descriptions.Item>
                                <Descriptions.Item label="Enrollment price">
                                    {Number(contract.enrollment_fixed_price)
                                        ? formatIncome(contract.enrollment_fixed_price as string, "USD")
                                        : "Free"}
                                </Descriptions.Item>
                                <Descriptions.Item label="Welcome message">{contract.welcome_message || "none"}</Descriptions.Item>
                                <Descriptions.Item label="Slug">
                                    <Typography.Text code>{contract.slug}</Typography.Text>
                                </Descriptions.Item>
                                {contract.description && (
                                    <Descriptions.Item label="Description" span={2}>
                                        <span style={{ whiteSpace: "pre-wrap" }}>{richTextToPlain(contract.description)}</span>
                                    </Descriptions.Item>
                                )}
                            </Descriptions>
                        </Card>
                    </Col>
                    <Col span={24}>
                        <ContractCourseware contractUrl={contractUrl} contract={contract} setupStatus={setupStatus} waitingForCodes={waitingForCodes} refresh={refresh} />
                    </Col>
                    <Col span={24}>
                        <ContractCodes
                            contractUrl={contractUrl}
                            contract={contract}
                            existingCodes={setupStatus?.enrollment_codes.existing}
                            refresh={refresh}
                        />
                    </Col>
                </Row>
            )}
        </Show>
    );
};
