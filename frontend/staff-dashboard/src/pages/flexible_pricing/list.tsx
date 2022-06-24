import { useUpdate, CrudFilters, HttpError } from "@pankod/refine-core";
import React from "react"
const {  useState  } = React;
import {
    Button,
    List,
    DateField,
    Table,
    useTable,
    Space, 
    FilterDropdown,
    Select,
    useSelect,
    FormProps,
    Form,
    Input, 
    Icons,
    Row,
    Col,
    Card,
    Modal
} from "@pankod/refine-antd";

import { IFlexiblePriceRequest, IFlexiblePriceRequestFilters } from "interfaces";
import { Type } from "typescript";

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

const All_Justifications = [
    {
        label: 'OK',
        value: 'Documents in order'
    },
    {
        label: 'NOT_NOTARIZED',
        value: 'Docs not notarized'
    },
    {
        label: 'INSUFFICIENT',
        value: 'Insufficient docs'
    },
    {
        label: 'INCOME_INACCURATE',
        value: 'Inaccurate income reported'
    },
    { 
        label: 'COUNTRY_INACCURATE',
        value: 'Inaccurate country reported'
    },
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
    const [modaldata, setmodaldata] = useState({} as IFlexiblePriceRequest);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const mutationResult = useUpdate<IFlexiblePriceRequest>();
    const [justification, setJustification] = useState("OK");
    const { mutate, isLoading: mutateIsLoading } = mutationResult;
    const handleUpdate = (item: IFlexiblePriceRequest, status: string) => {
        mutate({ 
            resource: "flexible_pricing/applications_admin",
            id: item.id,
            mutationMode: "undoable",
            values: { ...item, status }
        });
    };

    const showModal = (record: IFlexiblePriceRequest, action: string) => {
        const newRecord = {...record, 'action': action}
        setmodaldata(newRecord);
        setIsModalVisible(true);
    };

    const handleOk = () => {
        modaldata['justification'] = justification
        handleUpdate(modaldata, modaldata.action)
        setIsModalVisible(false);
    };

    const handleCancel = () => {
        setIsModalVisible(false);
    };

    const handleChange = (e: any) => {
        setJustification(e.target.options[e.target.selectedIndex].value)
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
                                            <Modal title="Flexible Pricing | Management" visible={isModalVisible} onOk={() => handleOk()} onCancel={handleCancel}>
                                                    <div>
                                                        <strong>Are you sure you want to <u>{modaldata.action == "skipped" ? "deny": String(modaldata.action).replace(/d|ped$/, '') }</u> the request?</strong>
                                                        {modaldata.action == "skipped" ? <div>User will be notified by email of the denial </div> : null}
                                                    </div>
                                                    <br></br>
                                                    <p>
                                                        <strong>Current Status:</strong>
                                                        <div>{modaldata.status}</div>
                                                    </p>
                                                    <p>
                                                        <strong>Income USD:</strong>
                                                        <div>{modaldata.income_usd}</div>
                                                    </p>
                                                    <p>
                                                        <strong>Original Income:</strong>
                                                        <div>{modaldata.original_income}</div>
                                                    </p>
                                                    <p>
                                                        <strong>Original Currency:</strong>
                                                        <div>{modaldata.original_currency}</div>
                                                    </p>
                                                    <p>
                                                        <strong>Country of Income:</strong>
                                                        <div>{modaldata.country_of_income}</div>
                                                    </p>
                                                    <p>
                                                        <span>
                                                            <strong>Justification:</strong>
                                                        </span>
                                                        <select onChange={(e) => handleChange(e)} style={{ marginLeft: "20px" }}>
                                                            {All_Justifications.map((option) => (
                                                            <option value={option.value} selected={justification == option.value}>{option.value}</option>
                                                            ))}
                                                        </select>
                                                    </p>
                                                </Modal>
                                        </div>
                                    );
                                }}
                            />
                        </Table>
                    </List>
                </Col>
            </Row>
        </div>
    );
};
