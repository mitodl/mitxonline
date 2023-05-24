import {
    List,
    DateField,
    ShowButton,
    Table,
    useTable,
    Space,
    EditButton,
    Tag,
    Row,
    Col,
    Card,
    Button,
} from "@pankod/refine-antd";
import { CrudFilters, HttpError, useInvalidate, useNavigation } from "@pankod/refine-core";

import { DiscountFilterForm } from "components/discounts/filter_form";

import { IDiscount, IDiscountFilters } from "interfaces";

export const DiscountList: React.FC = () => {
    const invalidate = useInvalidate()
    const navigation = useNavigation()
    const {tableQueryResult, tableProps, searchFormProps} = useTable<
        IDiscount,
        HttpError,
        IDiscountFilters
    >({
        resource: 'discounts',
        initialCurrent: 1,
        initialPageSize: 40,
        onSearch: (params) => {
            const filters: CrudFilters = [];
            const { q, redemption_type, payment_type, is_redeemed } = params;

            filters.push({
                field: 'q',
                operator: 'eq',
                value: q
            });

            filters.push({
                field: 'redemption_type',
                operator: 'eq',
                value: redemption_type
            });

            filters.push({
                field: 'payment_type',
                operator: 'eq',
                value: payment_type
            });

            filters.push({
                field: 'is_redeemed',
                operator: 'eq',
                value: is_redeemed
            });

            return filters;
        }
    });

    const refreshList = () => {
        tableQueryResult.refetch()
    }

    return (
        <div>
            <Row gutter={[10, 10]}>
                <Col sm={24}>
                    <Card title="Find Records">
                        <DiscountFilterForm formProps={searchFormProps} />
                    </Card>
                </Col>
            </Row>

            <Row gutter={[10, 10]}>
                <Col sm={24}>
                    <List>
                        <Row justify="end" gutter={[10, 10]}>
                            <Col sm={24}>
                                <Button style={{ "float": "right", "marginBottom": "5px" }} onClick={() => { navigation.push("discounts/create_batch"); }}>Create Batch</Button>
                            </Col>
                        </Row>

                        <Table {...tableProps} rowKey="id">
                            <Table.Column
                                dataIndex="discount_code"
                                title="Discount Code"
                                render={(value, record: IDiscount) => {
                                    return (<Space>{value} {record?.payment_type === "financial-assistance" ? (<Tag color="green">Financial Assistance Tier</Tag>) : null}</Space>)
                                }} />
                            <Table.Column
                                dataIndex="amount"
                                title="Amount"
                                render={(value, record: any) => parseFloat(value).toLocaleString('en-US') + ' ' + record?.discount_type }
                            />
                            <Table.Column
                                dataIndex="redemption_type"
                                title="Discount Type"
                                render={(value, record: any) => {
                                    return (<Space>{value} {record?.redemption_type !== "unlimited" && record?.is_redeemed ? (<Tag color="red">Redeemed</Tag>) : null}</Space>)
                                }}
                            />
                            <Table.Column
                                dataIndex="payment_type"
                                title="Payment Type"
                                render={(value, record: any) => {
                                    return (<Space>{value}</Space>)
                                }}
                            />
                            <Table.Column
                                dataIndex="activation_date"
                                title="Active From"
                                render={(value) => value ? (<DateField format="LLL" value={value} />) : (<em>---</em>)}
                            />
                            <Table.Column
                                dataIndex="expiration_date"
                                title="Expires"
                                render={(value) => value ? (<DateField format="LLL" value={value} />) : (<em>---</em>)}
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
                    </Col>
            </Row>
        </div>
    );
};
