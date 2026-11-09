import React from "react";
import { Create } from "@refinedev/antd";
import { useApiUrl, useCustomMutation, useGo, useParsed } from "@refinedev/core";
import { Form } from "antd";

import { apiErrorNotification, contractPath, contractsUrl } from "components/b2b/constants";
import { ContractForm, IContractForm, formToPayload } from "components/b2b/contract_form";
import { IProvisionedContract } from "interfaces";

export const ContractCreate: React.FC = () => {
    const { params } = useParsed<{ orgKey: string }>();
    const orgKey = params?.orgKey as string;
    const apiUrl = useApiUrl();
    const go = useGo();
    const [form] = Form.useForm<IContractForm>();
    const { mutate, isLoading } = useCustomMutation<IProvisionedContract>();

    const onFinish = (values: IContractForm) =>
        mutate(
            {
                url: `${contractsUrl(apiUrl, orgKey)}/`,
                method: "post",
                values: formToPayload(values),
                successNotification: {
                    type: "success",
                    message: `${values.name} created`,
                    description: "Add its programs and courses next.",
                },
                errorNotification: apiErrorNotification("Could not create the contract"),
            },
            { onSuccess: ({ data }) => go({ to: contractPath(orgKey, data.id) }) },
        );

    return (
        <Create title={`Add contract to ${orgKey}`} saveButtonProps={{ onClick: () => form.submit(), loading: isLoading }}>
            <ContractForm form={form} onFinish={onFinish} creating />
        </Create>
    );
};
