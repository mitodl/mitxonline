import { 
    Table,
    useTable,
    List,
    DateField,
} from "@pankod/refine-antd";
import moment from "moment";

export const RedemptionList = (props: any) => {
    const { record } = props
    const { tableProps } = useTable({
        resource: `discounts/${record?.id}/redemptions`
    });

    return (
        <List title="Redemptions" canCreate={false}>
            <Table {...tableProps} rowKey="id">
                <Table.Column dataIndex="id" title="ID"></Table.Column>
                <Table.Column 
                    dataIndex="redeemed_by" 
                    title="Redeemed By"
                    render={(value) => {
                        return value.username;
                    }}
                ></Table.Column>
                <Table.Column 
                    dataIndex="redeemed_on" 
                    title="Redeemed On"
                    render={(value) => <DateField format="LLL" value={value} />}
                ></Table.Column>
            </Table>
        </List>
    );
}