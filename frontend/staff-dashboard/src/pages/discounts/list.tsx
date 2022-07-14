import {
    List,
    DateField,
    ShowButton,
    Table,
    useTable,
    Space, 
    EditButton,
    Tag,
} from "@pankod/refine-antd";

import { IDiscount } from "interfaces";

export const DiscountList: React.FC = () => {
    const {tableProps} = useTable<IDiscount>({
        resource: 'discounts',
        initialCurrent: 1,
        initialPageSize: 40,
    });
    
    return (
        <List>
            <Table {...tableProps} rowKey="id">
                <Table.Column 
                    dataIndex="discount_code" 
                    title="Discount Code"
                    render={(value, record: IDiscount) => { 
                        return (<Space>{value} {record?.for_flexible_pricing ? (<Tag color="green">Flexible Pricing Tier</Tag>) : null}</Space>)
                    }} />
                <Table.Column
                    dataIndex="amount"
                    title="Amount"
                    render={(value, record: any) => parseFloat(value).toLocaleString('en-US') + ' ' + record?.discount_type }
                />
                <Table.Column
                    dataIndex="discount_type"
                    title="Discount Type"
                />
                <Table.Column
                    dataIndex="createdAt"
                    title="Created At"
                    render={(value) => <DateField format="LLL" value={value} />}
                />
                <Table.Column<IDiscount>
                    title="Actions"
                    dataIndex="actions"
                    render={(_text, record): React.ReactNode => {
                        return (
                            <Space>
                                <ShowButton
                                    size="small"
                                    recordItemId={record.id}
                                    hideText
                                />
                                <EditButton
                                    size="small"
                                    recordItemId={record.id}
                                    hideText
                                />
                            </Space>
                        );
                    }}
                />
            </Table>
        </List>
    );
};