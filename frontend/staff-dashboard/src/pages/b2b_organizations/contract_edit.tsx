import React from "react";
import { Edit } from "@refinedev/antd";
import { useApiUrl, useCustom, useCustomMutation, useGo, useParsed } from "@refinedev/core";
import { Form } from "antd";

import { apiErrorNotification, contractPath, contractsUrl } from "components/b2b/constants";
import { ContractForm, IContractForm, contractToForm, formToPayload } from "components/b2b/contract_form";
import { IProvisionedContract } from "interfaces";

export const ContractEdit: React.FC = () => {
    const { params } = useParsed<{ orgKey: string; contractId: string }>();
    const orgKey = params?.orgKey as string;
    const contractId = params?.contractId as string;
    const apiUrl = useApiUrl();
    const go = useGo();
    const [form] = Form.useForm<IContractForm>();
    const url = `${contractsUrl(apiUrl, orgKey)}/${contractId}/`;
    // Never cached: the form must start from the contract as it is now, not
    // from a copy the contract page fetched before somebody else's edit.
    const { data, isLoading: loading } = useCustom<IProvisionedContract>({
        url,
        method: "get",
        queryOptions: { cacheTime: 0 },
    });
    const { mutate, isLoading: saving } = useCustomMutation<IProvisionedContract>();
    const contract = data?.data;

    const onFinish = (values: IContractForm) =>
        mutate(
            {
                url,
                method: "patch",
                values: formToPayload(values),
                successNotification: { type: "success", message: `${values.name} saved` },
                errorNotification: apiErrorNotification("Could not save the contract"),
            },
            { onSuccess: () => go({ to: contractPath(orgKey, contractId) }) },
        );

    return (
        <Edit
            title={`Edit ${contract?.name ?? "contract"}`}
            isLoading={loading}
            saveButtonProps={{ onClick: () => form.submit(), loading: saving }}
            headerButtons={() => null}
        >
            {contract && <ContractForm form={form} onFinish={onFinish} initialValues={contractToForm(contract)} creating={false} />}
        </Edit>
    );
};
