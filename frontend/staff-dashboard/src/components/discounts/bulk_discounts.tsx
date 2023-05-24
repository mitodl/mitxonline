import {
  Form,
  Input,
  InputNumber,
  Select,
  DatePicker,
} from "@pankod/refine-antd";
import dayjs from 'dayjs';

interface IBulkDiscountFormProps {
  formProps: any;
}

export const BulkDiscountForm = (props: IBulkDiscountFormProps) => {
  const { formProps } = props;

  return (<>
    <Form {...formProps} layout="vertical">
        <Form.Item label="Prefix" name="prefix">
            <Input />
        </Form.Item>
        <Form.Item label="Codes to Create" name="count">
            <InputNumber precision={0} />
        </Form.Item>
        <Form.Item label="Redemption Type" name="redemption_type">
            <Select options={[
                { label: 'Unlimited', value: 'unlimited' },
                { label: 'One-Time', value: 'one-time' },
                { label: 'One Time Per User', value: 'one-time-per-user' },
            ]}></Select>
        </Form.Item>
        <Form.Item noStyle shouldUpdate={(prev, cur) => prev.redemption_type !== cur.redemption_type}>
        {({ getFieldValue }) => getFieldValue('redemption_type') === 'unlimited' ? (
            <Form.Item label="Maximum Redemptions" name="max_redemptions">
                <InputNumber precision={0} min={0} />
            </Form.Item>
        ) : null}
        </Form.Item>
        <Form.Item label="Discount Type" name="discount_type">
            <Select options={[
                { label: 'Percent Off', value: 'percent-off' },
                { label: 'Dollars Off', value: 'dollars-off' },
                { label: 'Fixed Price', value: 'fixed-price' },
            ]}></Select>
        </Form.Item>
        <Form.Item label="Amount" name="amount">
            <InputNumber precision={2} />
        </Form.Item>
        <Form.Item label="Payment Type" name="payment_type">
            <Select options={[
                { label: 'marketing', value: 'marketing' },
                { label: 'sales', value: 'sales' },
                { label: 'financial-assistance', value: 'financial-assistance' },
                { label: 'customer-support', value: 'customer-support' },
                { label: 'staff', value: 'staff' },
                { label: 'legacy', value: 'legacy' }
            ]}></Select>
        </Form.Item>
        <Form.Item label="Activation Date" name="activates">
            <Input type="datetime-local" />
        </Form.Item>

        <Form.Item label="Expiration Date" name="expires">
            <Input type="datetime-local" />
        </Form.Item>
    </Form>
  </>);
};
