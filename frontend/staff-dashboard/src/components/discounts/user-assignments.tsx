import {
    Table,
    useTable,
    List,
    Button,
    Modal,
    Row,
    Col,
    Input,
} from "@pankod/refine-antd";
import { useUpdate, useDelete } from "@pankod/refine-core";
import { PlusSquareOutlined } from "@ant-design/icons";
import { useState } from "react";

import type { IUser, IUserDiscount } from "interfaces";

interface IUserAssignmentsTableProps {
    record: any;
    isManagement?: boolean;
}

interface IUserAssignmentResultProps {
    searchTerm: string;
    onAdd: Function;
}

const UserResult = (props: IUserAssignmentResultProps) => {
    const { searchTerm, onAdd } = props;
    const { tableProps } = useTable<IUser>({
        resource: 'user_search',
        permanentFilter: [{
            field: "search",
            operator: "eq",
            value: searchTerm
        }]
    });

    return (<Table {...tableProps} rowKey="id">
        <Table.Column
            dataIndex="id"
            title="ID" />
        <Table.Column
            dataIndex="name"
            title="Name"
        />
        <Table.Column
            dataIndex="email"
            title="Email"
        />
        <Table.Column
            dataIndex="id"
            title=""
            render={(value, record) => (<button onClick={() => onAdd(record)}>Add</button>)}
        />
    </Table>);
}


export const UserAssignments = (props: IUserAssignmentsTableProps) => {
    const { record, isManagement } = props

    if (record === undefined) {
        return null;
    }

    const { tableProps } = useTable({
        resource: `discounts/${record?.id}/assignees`
    });
    const { mutate: updateUserList } = useUpdate<any>();
    const { mutate: deleteUserList } = useDelete<any>();
    const [showAddModal, setShowAddModal] = useState(false);
    const [searchTerm, setSearchTerm] = useState("");

    const performFilter = (ev: any) => {
        setSearchTerm(ev.target.value);
    }

    const hndAddUser = (user: IUser) => {
        updateUserList({
            id: record.id,
            resource: `discounts/${record?.id}/assignees`,
            values: { user_id: user.id }
        });
    }

    const hndRemoveUser = (user: IUser) => {
        deleteUserList({
            id: user.id,
            resource: `discounts/${record?.id}/assignees`,
        });
    }

    const customButtons = isManagement ? (<Button size="middle" onClick={() => setShowAddModal(true)}><PlusSquareOutlined /> Assign User</Button>) : null;

    return (<>
        <List title="Assigned Users" resource="discounts/user" canCreate={false} pageHeaderProps={{ extra: (customButtons)}}>
            <Table {...tableProps} rowKey="id">
                <Table.Column dataIndex="id" title="ID"></Table.Column>
                <Table.Column dataIndex="user" title="User" render={(value: any) => value.name}></Table.Column>
                <Table.Column dataIndex="user" title="Email" render={(value: any) => value.email}></Table.Column>
                {isManagement ? (<Table.Column dataIndex="product" title="" render={(value, record: IUserDiscount) => (<Button size="small" onClick={() => hndRemoveUser(record.user)}>Delete</Button>)}></Table.Column>) : null }
            </Table>
        </List>

        <Modal
            title="Assign Users"
            visible={showAddModal}
            onCancel={() => setShowAddModal(false)}
            onOk={() => setShowAddModal(false)}
            footer={[
                <Button key="submit" type="primary" onClick={() => setShowAddModal(false)}>Close</Button>
            ]}
        >
            <Row>
                <Col sm={24}>
                    <p>Assigning a user to a discount automatically applies the discount when the user checks out. Other users can still apply the discount manually if they're aware of the discount code.</p>

                    <label>
                        Search Users:
                        <Input onChange={performFilter} allowClear={true}></Input>
                    </label>

                    {searchTerm !== "" ? (<UserResult onAdd={hndAddUser} searchTerm={searchTerm}></UserResult>) : null}
                </Col>
            </Row>
        </Modal>
    </>);
}
