import { useMany } from "@pankod/refine-core";
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
} from "@pankod/refine-antd";

import { IFlexiblePriceRequest, IFlexiblePriceStatus } from "interfaces";

export const FlexiblePricingList: React.FC = () => {
    const {tableProps} = useTable<IFlexiblePriceRequest>({ resource: 'flexible_pricing/applications_admin' });

    return (
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
                                placeholder="Select Status" 
                                options={[
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
                            ]} />
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
    );
};