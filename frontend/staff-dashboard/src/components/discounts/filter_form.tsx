import React from "react"
import {
    Button,
    Select,
    FormProps,
    Form,
    Input,
    Icons,
} from "@pankod/refine-antd";
import {Discount_Redemption_Types} from "../../constants";

export const DiscountFilterForm: React.FC<{ formProps: FormProps }> = ({ formProps }) => {
  const DiscountPaymentTypesOpts = [
    {
        label: '',
        value: '',
    },
    {
        label: 'marketing',
        value: 'marketing',
    },
    {
        label: 'sales',
        value: 'sales',
    },
    {
        label: 'financial-assistance',
        value: 'financial-assistance',
    },
    {
        label: 'customer-support',
        value: 'customer-support',
    },
    {
        label: 'staff',
        value: 'staff',
    },
    {
        label: 'legacy',
        value: 'legacy',
    },
  ]
  const redemptionOpts = [
    { label: '', value: '' }, { label: 'Redeemed', value: 'yes' }, { label: 'Not Redeemed', value: 'no' }
  ]

  return (
      <Form layout="inline" {...formProps}>
          <Form.Item label="Search by Code" name="q">
              <Input
                placeholder="Discount Code"
                style={{ minWidth: 400 }}
                prefix={<Icons.SearchOutlined />}
                allowClear={true}
            ></Input>
          </Form.Item>
          <Form.Item label="Search by Type" name="redemption_type">
              <Select
                  options={Discount_Redemption_Types}
                  style={{ minWidth: 250 }}
                  allowClear={true} />
          </Form.Item>
          <Form.Item label="Search by Payment Type" name="payment_type">
              <Select
                  options={DiscountPaymentTypesOpts}
                  style={{ minWidth: 250 }}
                  allowClear={true} />
          </Form.Item>
          <Form.Item label="Filter by Redemption Status" name="is_redeemed">
              <Select
                  options={redemptionOpts}
                  style={{ minWidth: 250 }}
                  allowClear={true} />
          </Form.Item>
          <Form.Item>
              <Button htmlType="submit" type="primary">
                  Find Records
              </Button>
          </Form.Item>
      </Form>
  )
}
