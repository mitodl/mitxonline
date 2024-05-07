import {
    useForm,
    Form,
    Input,
    InputNumber,
    Select,
    Edit,
 } from "@pankod/refine-antd";
import { DiscountForm } from "components/discounts/discounts";

import { IDiscount } from "interfaces";


export const DiscountEdit = () => {
    const { formProps, saveButtonProps, queryResult } = useForm<IDiscount>();
    const discount_type = queryResult?.data?.data.discount_type

    return (
        <div>
            <Edit saveButtonProps={saveButtonProps}>
                <DiscountForm formProps={formProps}></DiscountForm>
            </Edit>
        </div>
    );
};
