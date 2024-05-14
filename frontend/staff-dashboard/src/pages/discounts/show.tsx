import { useShow } from "@pankod/refine-core";
import { Show, Typography, Tag, Row, Col, Space } from "@pankod/refine-antd";
import dayjs from "dayjs";

import { RedemptionList, UserAssignments, Products } from "components/discounts";
import { FinAidTiers } from "components/discounts/fin_aid_tiers";
const { Title, Text } = Typography;

export const DiscountShow = () => {
    const { queryResult } = useShow();
    const { data, isLoading } = queryResult;
    const record = data?.data;

    return (
        <Show isLoading={isLoading}>
            <h2>
                <Space>
                    Discount Detail
                    { record?.payment_type === 'financial-assistance' ? (<Tag color="green">Financial Assistance Tier</Tag>) : null }
                    { record?.redemption_type !== "unlimited" && record?.is_redeemed ? (<Tag color="red">Redeemed</Tag>) : null }
                </Space>
            </h2>

            <Row>
                <Col span={12}>
                    <Title level={5}>Code</Title>
                    <Text>{record?.discount_code}</Text>

                    <Title level={5}>Redemption Type</Title>
                    <Text>
                        <Tag>{record?.redemption_type}</Tag>
                    </Text>

                    <Title level={5}>Payment Type</Title>
                    <Text>
                        <Tag>{record?.payment_type}</Tag>
                    </Text>

                    <Title level={5}>Amount</Title>
                    <Text>{record?.amount} {record?.discount_type}</Text>
                </Col>
                <Col span={12}>
                    {record?.redemption_type === 'unlimited' && record?.max_redemptions > 0 ? (<>
                        <Title level={5}>Max Redemptions</Title>
                        <Text>
                            {record.max_redemptions}
                        </Text>
                    </>) : null}

                    <Title level={5}>Activation Date</Title>
                    <Text>{record?.activation_date ? dayjs(record.activation_date).format("YYYY-MM-DD HH:mm:ss") : (<em>Always Available</em>)}</Text>

                    <Title level={5}>Expiration Date</Title>
                    <Text>{record?.expiration_date ? dayjs(record.expiration_date).format("YYYY-MM-DD HH:mm:ss") : (<em>Always Available</em>)}</Text>
                </Col>
            </Row>

            {record ? <RedemptionList record={record} key={`redemptions-${record?.id}`} /> : null}

            {record && record.payment_type === 'financial-assistance' ? <FinAidTiers record={record} key={`tiers-${record?.id}`} /> : null}

            {record ? <UserAssignments record={record} key={`assignees-${record?.id}`} /> : null}

            {record ? <Products record={record} key={`products-${record?.id}`} /> : null}
        </Show>
    );
};
