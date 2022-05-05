import { useShow, useOne } from "@pankod/refine-core";
import { Show, Typography, Tag,
    Table,
    useTable,
 } from "@pankod/refine-antd";
import { IDiscountRedemption } from "interfaces";
import { RedemptionList, UserAssignments } from "components/discounts";
const { Title, Text } = Typography;

export const DiscountShow = () => {
    const { queryResult } = useShow();
    const { data, isLoading } = queryResult;
    const record = data?.data;

    return (
        <Show isLoading={isLoading}>
            <h2>Discount Detail</h2>
            
            <Title level={5}>Code</Title>
            <Text>{record?.discount_code}</Text>

            <Title level={5}>Redemption Type</Title>
            <Text>
                <Tag>{record?.redemption_type}</Tag>
            </Text>

            <Title level={5}>Amount</Title>
            <Text>{record?.amount} {record?.discount_type}</Text>

            {record ? <UserAssignments record={record} key={record?.user} /> : null}

            {record ? <RedemptionList record={record} key={record?.id} /> : null}
        </Show>
    );
};