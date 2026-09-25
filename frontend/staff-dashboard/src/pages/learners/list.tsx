import { List, TagField, DateField, useTable } from "@refinedev/antd";
import { Table } from "antd";

export const PostList: React.FC = () => {
    const { tableProps } = useTable();
    return (
        <List>
            <Table {...tableProps} rowKey="id">
                <Table.Column dataIndex="title" title="title" />
                <Table.Column
                    dataIndex="status"
                    title="status"
                    render={(value) => <TagField value={value} />}
                />
                <Table.Column
                    dataIndex="createdAt"
                    title="createdAt"
                    render={(value) => <DateField format="LLL" value={value} />}
                />
            </Table>
        </List>
    );
};
