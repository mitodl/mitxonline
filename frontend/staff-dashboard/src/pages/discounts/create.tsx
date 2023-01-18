import { 
    useForm,
    Create,
 } from "@pankod/refine-antd";
import { DiscountForm } from "components/discounts/discounts";

import { IDiscount } from "interfaces";

export const DiscountCreate = () => {
    const { formProps, saveButtonProps } = useForm<IDiscount>();

    return (
        <Create saveButtonProps={saveButtonProps}>
            <DiscountForm formProps={formProps}></DiscountForm>
        </Create>
    );
};