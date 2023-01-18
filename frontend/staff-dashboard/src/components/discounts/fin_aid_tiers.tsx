import { 
    Table,
    useTable,
    List,
} from "@pankod/refine-antd";

export const FinAidTiers = (props: any) => {
    const { record } = props

    if (record === undefined) {
        return null;
    }

    const { tableProps } = useTable({
        resource: `discounts/${record?.id}/tiers`
    });

    return (
        <List title="Financial Assistance Tiers" resource="discounts/tiers" canCreate={false}>
            <Table {...tableProps} rowKey="id">
                <Table.Column 
                    dataIndex="current" 
                    title="Current?"
                    render={(value) => { return value ? "Yes" : "No" }} 
                />
                <Table.Column 
                    dataIndex="courseware_object" 
                    title="Courseware"
                    render={(value) => (<>{value.title}<br />{value?.readable_id}</>)}
                />
                <Table.Column 
                    dataIndex="income_threshold_usd" 
                    title="Income Threshold (USD)"
                    render={(value) => value?.toLocaleString("en-US", { style: "currency", currency: "USD" })} 
                />
            </Table>
        </List>
    );
}