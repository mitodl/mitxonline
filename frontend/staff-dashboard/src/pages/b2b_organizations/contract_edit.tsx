import React from "react";
import { Edit } from "@refinedev/antd";
import { useApiUrl, useCustom, useCustomMutation, useGo, useParsed } from "@refinedev/core";
import { Form, Result } from "antd";

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
    // This shares a cache entry with the contract page, which may have fetched
    // its copy long before somebody else's edit. The form keeps whatever it
    // first renders with, so wait for the fetch this page made.
    const { data, isFetchedAfterMount, isError } = useCustom<IProvisionedContract>({ url, method: "get" });
    const { mutate, isLoading: saving } = useCustomMutation<IProvisionedContract>();
    const contract = isFetchedAfterMount ? data?.data : undefined;

    const onFinish = (values: IContractForm) => {
        // Send only what the operator changed, so a field somebody else
        // changed since the form loaded is not put back.
        const original = formToPayload(contractToForm(contract as IProvisionedContract)) as Record<string, unknown>;
        const changes = Object.fromEntries(
            Object.entries(formToPayload(values)).filter(([field, value]) => value !== original[field]),
        );
        if (Object.keys(changes).length === 0) {
            go({ to: contractPath(orgKey, contractId) });
            return;
        }
        mutate(
            {
                url,
                method: "patch",
                values: changes,
                successNotification: { type: "success", message: `${values.name} saved` },
                errorNotification: apiErrorNotification("Could not save the contract"),
            },
            { onSuccess: () => go({ to: contractPath(orgKey, contractId) }) },
        );
    };

    return (
        <Edit
            title={`Edit ${contract?.name ?? "contract"}`}
            isLoading={!contract && !isError}
            saveButtonProps={{ onClick: () => form.submit(), loading: saving }}
            headerButtons={() => null}
        >
            {isError && <Result status="warning" title={`Could not load contract ${contractId} of ${orgKey}`} />}
            {contract && <ContractForm form={form} onFinish={onFinish} initialValues={contractToForm(contract)} creating={false} />}
        </Edit>
    );
};
