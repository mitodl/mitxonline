import { 
    Table,
    useTable,
    List,
} from "@pankod/refine-antd";

export const UserAssignments = (props: any) => {
    const { record } = props

    if (record === undefined) {
        return null;
    }

    const { tableProps } = useTable({
        resource: `discounts/${record?.id}/assignees`
    });

    return (
        <List title="Assigned Users" resource="discounts/user" canCreate={false}>
            <Table {...tableProps} rowKey="id">
                <Table.Column dataIndex="id" title="ID"></Table.Column>
                <Table.Column dataIndex="user" title="User" render={(value: any) => value.name}></Table.Column>
            </Table>
        </List>
    );
}