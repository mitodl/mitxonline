import { useUpdate, useNotification, CrudFilters, HttpError } from "@pankod/refine-core";
import React from "react"
const { useState } = React;
import {
    Button,
    List,
    DateField,
    Table,
    useTable,
    Space, 
    FilterDropdown,
    Select,
    FormProps,
    Form,
    Input, 
    Icons,
    Row,
    Col,
    Card
} from "@pankod/refine-antd";

import { IFlexiblePriceRequest, IFlexiblePriceRequestFilters } from "interfaces";
import { FlexiblePricingStatusModal } from "components/flexiblepricing/statusmodal";

const FlexiblePricingStatuses = [
    {
        label: 'Created',
        value: 'created'
    },
    {
        label: 'Approved',
        value: 'approved'
    },
    {
        label: 'Auto-Approved',
        value: 'auto-approved'
    },
    {
        label: 'Pending Manual Approval',
        value: 'pending-manual-approval'
    },
    { 
        label: 'Skipped',
        value: 'skipped'
    },
    { 
        label: 'Reset',
        value: 'reset'
    }
];

const FlexiblePricingStatusText = "Select Status";

const FlexiblePricingFilterForm: React.FC<{ formProps: FormProps }> = ({ formProps }) => {
    return (
        <Form layout="inline" {...formProps}>
            <Form.Item label="Search by Name" name="q">
                <Input placeholder="Name, username, email address" prefix={<Icons.SearchOutlined />}></Input>
            </Form.Item>
            <Form.Item label="Search by Status" name="status">
                <Select
                    style={{ minWidth: 200 }}
                    placeholder={FlexiblePricingStatusText}
                    options={FlexiblePricingStatuses} />
            </Form.Item>
            <Form.Item>
                <Button htmlType="submit" type="primary">
                    Find Records
                </Button>
            </Form.Item>
        </Form>
    )
}

export const FlexiblePricingList: React.FC = () => {
    const { open: displayToast } = useNotification();

    const {tableProps, searchFormProps} = useTable<
        IFlexiblePriceRequest,
        HttpError, 
        IFlexiblePriceRequestFilters
    >({ 
        resource: 'flexible_pricing/applications_admin',
        onSearch: (params) => {
            const filters: CrudFilters = [];
            const { q, status } = params;

            filters.push({
                field: 'q',
                operator: 'eq',
                value: q
            });

            filters.push({
                field: 'status',
                operator: 'eq',
                value: status
            });

            return filters;
        }
    });

    const [modaldata, setModalData] = useState({} as IFlexiblePriceRequest);
    const [approveStatus, setApproveStatus] = useState('');

    const [isModalVisible, setIsModalVisible] = useState(false);
    
    const showModal = (record: IFlexiblePriceRequest, action: string) => {
        setModalData(record);
        setApproveStatus(action);
        setIsModalVisible(true);

    };

    return (
        <div>
            <Row gutter={[10, 10]}>
                <Col sm={24}>
                    <Card title="Find Records">
                        <FlexiblePricingFilterForm formProps={searchFormProps} />
                    </Card>
                </Col>
            </Row>

            <Row gutter={[10, 10]}>
                <Col sm={24}>
                    <List title="Flexible Pricing Requests">
                        <Table {...tableProps} rowKey="id">
                            <Table.Column 
                                dataIndex="user" 
                                title="Name/Location"
                                render={(value) => <div><strong>{value.name}</strong> <br /> {value.legal_address.country}</div>}
                            />
                            <Table.Column
                                dataIndex="status"
                                title="Status"
                            />
                            <Table.Column
                                dataIndex="income_usd"
                                title="Income (USD)"
                                render={(value) => parseFloat(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' })}
                            />
                            <Table.Column
                                dataIndex="date_exchange_rate"
                                title="Date Calculated"
                                render={(value) => <DateField format="LLL" value={value} />}
                            />
                            <Table.Column
                                dataIndex="original_currency"
                                title="Original Currency"
                            />
                            <Table.Column
                                dataIndex="date_documents_sent"
                                title="Documents Sent"
                                render={(value) => value ? <DateField format="LLL" value={value} /> : 'No Documents Sent'}
                            />
                            <Table.Column
                                dataIndex="justification"
                                title="Justification"
                                render={(value) => value}
                            />
                            <Table.Column<IFlexiblePriceRequest>
                                title="Actions"
                                dataIndex="actions"
                                render={(index, record) => {
                                    return (
                                        <div>
                                            <Space>
                                                <Button
                                                    type="primary"
                                                    onClick={() => showModal(record, "approved")}
                                                >
                                                    Approve
                                                </Button>
                                                <Button
                                                    type="dashed"
                                                    onClick={() => showModal(record, "reset")}
                                                >
                                                    Reset
                                                </Button>
                                                <Button danger
                                                    onClick={() => showModal(record, "skipped")}
                                                >
                                                    Deny
                                                </Button>
                                            </Space>
                                        </div>
                                    );
                                }}
                            />
                        </Table>
                    </List>
                </Col>
            </Row>
            {isModalVisible ? <FlexiblePricingStatusModal record={modaldata} status={approveStatus} onClose={() => {setIsModalVisible(false);}}></FlexiblePricingStatusModal> : null}
        </div>
    );
};
