import { useList } from "@pankod/refine-core";
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
  const FlexiblePricingCoursewareList: any[] | undefined = [];
  const DiscountList = useList({
      resource: "discounts",
  });
  if (DiscountList.data) {
      DiscountList.data.data.map(item => {
          FlexiblePricingCoursewareList.push({
              'label': item.readable_id,
              'value': item.type + ':' + item.id
          })
      })
  }

  const flexPriceOpts = [
    { label: '', value: '' }, { label: 'For Financial Assistance', value: true }, { label: 'Regular Discount', value: false }
  ]

  return (
      <Form layout="inline" {...formProps}>
          <Form.Item label="Search by Code" name="q">
              <Input placeholder="Discount Code" prefix={<Icons.SearchOutlined />}></Input>
          </Form.Item>
          <Form.Item label="Search by Type" name="redemption_type">
              <Select
                  style={{ minWidth: 200 }}
                  options={Discount_Redemption_Types}
                  allowClear={true} />
          </Form.Item>
          <Form.Item label="Search by Financial Assistance" name="for_flexible_pricing">
              <Select
                  style={{ minWidth: 250 }}
                  options={flexPriceOpts}
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
