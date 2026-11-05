import { useForm, Edit } from "@refinedev/antd";
import { Form, Input, InputNumber, Select } from "antd";
import { DiscountForm } from "components/discounts/discounts";

import { IDiscount } from "interfaces";


export const DiscountEdit = () => {
    const { formProps, saveButtonProps, query } = useForm<IDiscount>();
    const discount_type = query?.data?.data.discount_type

    return (
        <div>
            <Edit saveButtonProps={saveButtonProps}>
                <DiscountForm formProps={formProps}></DiscountForm>
            </Edit>
        </div>
    );
};
