import React from "react";
import { List, ShowButton, useTable } from "@refinedev/antd";
import { CrudFilters, HttpError } from "@refinedev/core";
import { Button, Card, Col, Form, FormProps, Input, Row, Select, Space, Table, Tag } from "antd";
import { SearchOutlined } from "@ant-design/icons";

import { ONBOARDING_STATES, PROVISIONING_RESOURCE, idpState, onboardingState } from "components/b2b/constants";
import { IOrganizationIdentityProvider, IProvisionedOrganization } from "interfaces";

interface IOrganizationFilters {
    q: string;
    onboarding_state: string;
}

const OrganizationFilterForm: React.FC<{ formProps: FormProps }> = ({ formProps }) => (
    <Form layout="inline" {...formProps}>
        <Form.Item label="Search" name="q">
            <Input placeholder="Name or org key" prefix={<SearchOutlined />} allowClear />
        </Form.Item>
        <Form.Item label="Onboarding state" name="onboarding_state">
            <Select
                allowClear
                style={{ minWidth: 220 }}
                options={ONBOARDING_STATES.map(({ value, label }) => ({ value, label }))}
            />
        </Form.Item>
        <Form.Item>
            <Button htmlType="submit" type="primary">Find</Button>
        </Form.Item>
    </Form>
);

export const OrganizationList: React.FC = () => {
    const { tableProps, searchFormProps } = useTable<IProvisionedOrganization, HttpError, IOrganizationFilters>({
        resource: PROVISIONING_RESOURCE,
        pagination: { pageSize: 25 },
        onSearch: ({ q, onboarding_state }) => {
            const filters: CrudFilters = [
                { field: "q", operator: "eq", value: q },
                { field: "onboarding_state", operator: "eq", value: onboarding_state },
            ];
            return filters;
        },
    });

    return (
        <Row gutter={[16, 16]}>
            <Col span={24}>
                <Card>
                    <OrganizationFilterForm formProps={searchFormProps} />
                </Card>
            </Col>
            <Col span={24}>
                <List title="B2B organizations">
                    <Table {...tableProps} rowKey="org_key">
                        <Table.Column dataIndex="name" title="Name" />
                        <Table.Column dataIndex="org_key" title="Org key" />
                        <Table.Column<IProvisionedOrganization>
                            title="Onboarding"
                            render={(_, record) => {
                                const state = onboardingState(record.onboarding?.state);
                                return state ? <Tag color={state.color}>{state.label}</Tag> : <Tag>Not tracked</Tag>;
                            }}
                        />
                        <Table.Column<IProvisionedOrganization>
                            title="Identity providers"
                            render={(_, record) =>
                                record.identity_providers.length === 0 ? (
                                    "None"
                                ) : (
                                    <Space wrap>
                                        {record.identity_providers.map((idp: IOrganizationIdentityProvider) => (
                                            <Tag key={idp.alias} color={idpState(idp.lifecycle_state)?.color}>
                                                {idp.alias}: {idpState(idp.lifecycle_state)?.label ?? idp.lifecycle_state}
                                            </Tag>
                                        ))}
                                    </Space>
                                )
                            }
                        />
                        <Table.Column<IProvisionedOrganization>
                            title="Actions"
                            render={(_, record) => <ShowButton hideText size="small" recordItemId={record.org_key} />}
                        />
                    </Table>
                </List>
            </Col>
        </Row>
    );
};
