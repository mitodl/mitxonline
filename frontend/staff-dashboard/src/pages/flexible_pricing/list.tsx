import { IResourceComponentsProps, useMany, CrudFilters, HttpError } from "@pankod/refine-core";
import {
    List,
    DateField,
    ShowButton,
    Table,
    useTable,
    Space, 
    EditButton,
    FilterDropdown,
    Select,
    useSelect,
    FormProps,
    Form,
    Input, 
    Button,
    Icons,
    Row,
    Col,
    Card,
} from "@pankod/refine-antd";

import { IFlexiblePriceRequest, IFlexiblePriceStatus, IFlexiblePriceRequestFilters } from "interfaces";

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
        <Form layout="vertical" {...formProps}>
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

    return (
        <div>
            <Row gutter={[10, 10]}>
                <Col sm={6}>
                    <Card title="Find Records">
                        <FlexiblePricingFilterForm formProps={searchFormProps} />
                    </Card>
                </Col>
                <Col sm={18}>
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
                                filterDropdown={(props) => (
                                    <FilterDropdown {...props}>
                                        <Select mode="multiple" 
                                            style={{ minWidth: 300 }}
                                            placeholder={FlexiblePricingStatusText}
                                            options={FlexiblePricingStatuses} />
                                    </FilterDropdown>
                                )}
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
                                dataIndex="createdAt"
                                title="Created At"
                                render={(value) => <DateField format="LLL" value={value} />}
                            />
                        </Table>
                    </List>
                </Col>
            </Row>
        </div>        
    );
};