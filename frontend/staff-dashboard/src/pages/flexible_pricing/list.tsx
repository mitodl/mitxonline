import { CrudFilters, HttpError, useInvalidate } from "@pankod/refine-core";
import React from "react"
const { useState } = React;
import {
    Button,
    List,
    DateField,
    Table,
    useTable,
    Space, 
    Select,
    FormProps,
    Form,
    Input, 
    Icons,
    Row,
    Col,
    Card
} from "@pankod/refine-antd";
import { ReloadOutlined } from "@ant-design/icons"
import { Spin } from "antd"

import { IFlexiblePriceRequest, IFlexiblePriceRequestFilters } from "interfaces";
import { FlexiblePricingStatusModal } from "components/flexiblepricing/statusmodal";
import { formatDiscount, formatIncome } from "utils";
import { financialAssistanceRequestStatus } from "../../constants";

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
        label: 'Denied',
        value: 'denied'
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
                    options={FlexiblePricingStatuses}
                    allowClear={true} />
            </Form.Item>
            <Form.Item>
                <Button htmlType="submit" type="primary">
                    Find Records
                </Button>
            </Form.Item>
        </Form>
    )
}

interface RefreshTableButtonProps {
    refreshList: any;
    isFetching: boolean;
}

const RefreshTableButton: React.FC<RefreshTableButtonProps> = (props) => {
    const { isFetching, refreshList } = props

    if (props.isFetching) {
        return (
            <Button onClick={props.refreshList}>
                <ReloadOutlined spin /> Refreshing...
            </Button>
        )
    }

    return (
        <Button onClick={props.refreshList}>
           <ReloadOutlined /> Refresh
        </Button>
    )
}

export const FlexiblePricingList: React.FC = () => {
    const invalidate = useInvalidate()
    const {tableQueryResult, tableProps, searchFormProps} = useTable<
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

    const formatStatus = (status: string) => {
        const result = FlexiblePricingStatuses.find((elem) => elem.value === status);

        if (result) {
            return result.label
        }

        return null
    }

    const refreshList = () => {
        tableQueryResult.refetch()
    }

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
                </Col>
            </Row>

            <Row gutter={[10, 10]}>
                <Col sm={24}>
                    <List 
                        title="Flexible Pricing Requests"
                        pageHeaderProps={{ subTitle: <RefreshTableButton isFetching={tableQueryResult.isFetching} refreshList={refreshList} /> }}
                    >
                        <Table {...tableProps} rowKey="id">
                            <Table.Column 
                                dataIndex="user" 
                                title="Name/Location"
                                render={(value) => <div><strong>{value.name}</strong> <br /> {value.email} <br /> {value.legal_address.country}</div>}
                            />
                            <Table.Column
                                dataIndex="status"
                                title="Status"
                                render={(value) => formatStatus(value)}
                            />
                            <Table.Column
                                dataIndex="courseware"
                                title="Courseware"
                                render={(value) => value.readable_id}
                            />
                            <Table.Column
                                dataIndex="income"
                                title="Income"
                                render={
                                (value) => <div className="income-usd">
                                    <span>
                                        { formatIncome(value.income_usd, "USD") }
                                        <br />
                                        { formatIncome(value.original_income, value.original_currency) }
                                    </span>
                                </div>
                            }
                            />
                            <Table.Column
                                dataIndex="date_exchange_rate"
                                title="Date Calculated"
                                render={(value) => <DateField format="l" value={value.toLocaleString()} />}
                            />
                            <Table.Column
                                dataIndex="discount"
                                title="Discount"
                                render={(value) => <div>{ formatDiscount(value) }</div>}
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
                                                    onClick={() => showModal(record, financialAssistanceRequestStatus.approved)}
                                                >
                                                    Approve
                                                </Button>
                                                <Button
                                                    type="dashed"
                                                    onClick={() => showModal(record, financialAssistanceRequestStatus.reset)}
                                                >
                                                    Reset
                                                </Button>
                                                <Button danger
                                                    onClick={() => showModal(record, financialAssistanceRequestStatus.denied)}
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
