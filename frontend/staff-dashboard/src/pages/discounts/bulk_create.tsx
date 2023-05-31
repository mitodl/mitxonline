import {
    useForm,
    Create,
 } from "@pankod/refine-antd";
import { BulkDiscountForm } from "components/discounts/bulk_discounts";
import { BulkDiscountResults } from "components/discounts/bulk_discount_results";
import { IBulkDiscount } from "interfaces";

export const BulkDiscountCreate = () => {
    const { formProps, saveButtonProps, mutationResult } = useForm<IBulkDiscount>({
      resource: 'discounts/create_batch',
      redirect: false,
      action: 'create',
    });

    return mutationResult && mutationResult.isSuccess ?
      (<BulkDiscountResults data={mutationResult.data.data} />) :
      (<Create title="Create Bulk Discounts" saveButtonProps={saveButtonProps}>
        <BulkDiscountForm formProps={formProps} />
      </Create>);
};
