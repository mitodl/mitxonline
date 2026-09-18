import { useForm, Create } from "@refinedev/antd";
import { BulkDiscountForm } from "components/discounts/bulk_discounts";
import { BulkDiscountResults } from "components/discounts/bulk_discount_results";
import { IBulkDiscount } from "interfaces";

export const BulkDiscountCreate = () => {
    const { formProps, saveButtonProps, mutation } = useForm<IBulkDiscount>({
      resource: 'discounts/create_batch',
      redirect: false,
      action: 'create',
    });

    return mutation.isSuccess && mutation.data ?
      (<BulkDiscountResults data={mutation.data.data} />) :
      (<Create title="Create Bulk Discounts" saveButtonProps={saveButtonProps}>
        <BulkDiscountForm formProps={formProps} />
      </Create>);
};
