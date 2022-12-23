import React from "react"
import {
    Button,
    Select,
    FormProps,
    Form,
    Input,
    Icons,
} from "@pankod/refine-antd";
import { Discount_Redemption_Types } from "../../constants";

export const DiscountFilterForm: React.FC<{ formProps: FormProps }> = ({ formProps }) => {
  const flexPriceOpts = [
    { label: '', value: '' }, { label: 'For Financial Assistance', value: 'yes' }, { label: 'Regular Discount', value: 'no' }
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
          <Form.Item label="Search by Financial Assistance" name="for_flexible_pricing">
              <Select
                  options={flexPriceOpts}
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
